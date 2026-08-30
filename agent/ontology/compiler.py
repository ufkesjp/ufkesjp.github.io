"""Ontology-grounded SQL compiler.

Nothing in this project executes free-form SQL. Every query the agent (or a
human at a REPL) can run goes through build_metric_query or
build_link_traversal_query, both of which validate every metric name, filter
field, grain dimension, and link name against the loaded Ontology before
touching a query string. Anything not present in the ontology raises
UnknownMetricError / UnknownFilterError / UnknownLinkError instead of
silently falling through to string interpolation of an unchecked name.

The only string interpolation into SQL text is of *column expressions and
table names the ontology itself defined* — filter *values* are always bound
as query parameters, never interpolated.
"""

from __future__ import annotations

from dataclasses import dataclass

from .schema import Ontology, load_ontology

AS_OF_DATE = "2026-08-29"  # fictional "today" the seed data was generated against
DELAM_MATURITY_DAYS = 90
SCRAP_UNIT_COST = 85.0  # dollars/deck, a modeling constant, not ontology data
ON_TIME_LEAD_DAYS = 10


class CompilerError(Exception):
    """Base class for all ontology-compiler validation failures."""


class UnknownMetricError(CompilerError):
    pass


class UnknownFilterError(CompilerError):
    pass


class UnknownGrainError(CompilerError):
    pass


class UnknownLinkError(CompilerError):
    pass


@dataclass
class MetricQuerySpec:
    """Everything the compiler needs to build SQL for one metric, expressed
    purely in terms of ontology-defined tables and columns."""

    from_clause: str
    aggregate_expr: str  # SQL expression producing the metric's `value` column
    grain_columns: dict[str, str]  # grain dim name -> SQL column expression
    filter_columns: dict[str, str]  # filter field name -> SQL column expression
    where_extra: str = ""  # always-applied predicate (e.g. maturity window)
    ctes: str = ""


def _metric_specs() -> dict[str, MetricQuerySpec]:
    return {
        "first_pass_yield": MetricQuerySpec(
            from_clause=(
                "quality_inspections qi "
                "JOIN production_batches b ON qi.batch_id = b.batch_id"
            ),
            aggregate_expr=(
                "SUM(qi.decks_passed) * 1.0 / NULLIF(SUM(qi.decks_inspected), 0)"
            ),
            grain_columns={
                "batch": "qi.batch_id",
                "press_line": "b.press_line_id",
                "month": "date_trunc('month', qi.inspection_date)",
            },
            filter_columns={
                "series": "b.series",
                "press_line_id": "b.press_line_id",
                "batch_id": "qi.batch_id",
            },
        ),
        "scrap_cost_per_batch": MetricQuerySpec(
            from_clause=(
                "quality_inspections qi "
                "JOIN production_batches b ON qi.batch_id = b.batch_id"
            ),
            aggregate_expr=(
                f"SUM((qi.decks_inspected - qi.decks_passed) * {SCRAP_UNIT_COST}) "
                "/ NULLIF(SUM(b.deck_count), 0)"
            ),
            grain_columns={
                "batch": "qi.batch_id",
                "press_line": "b.press_line_id",
                "month": "date_trunc('month', qi.inspection_date)",
            },
            filter_columns={
                "series": "b.series",
                "press_line_id": "b.press_line_id",
                "batch_id": "qi.batch_id",
            },
        ),
        "veneer_yield": MetricQuerySpec(
            ctes=(
                "WITH lot_usage AS ("
                "  SELECT lot_id, SUM(quantity_used) AS used"
                "  FROM batch_material_lots GROUP BY lot_id"
                ")"
            ),
            from_clause=(
                "material_lots ml JOIN lot_usage lu ON lu.lot_id = ml.lot_id"
            ),
            aggregate_expr="SUM(lu.used) * 1.0 / NULLIF(SUM(ml.quantity), 0)",
            grain_columns={
                "lot": "ml.lot_id",
                "supplier": "ml.supplier_id",
                "month": "date_trunc('month', ml.received_date)",
            },
            filter_columns={
                "supplier_id": "ml.supplier_id",
                "material_type": "ml.material_type",
            },
        ),
        "on_time_ship_rate": MetricQuerySpec(
            from_clause="orders o JOIN retail_accounts ra ON o.account_id = ra.account_id",
            aggregate_expr=(
                "SUM(CASE WHEN o.status != 'cancelled' AND o.ship_date IS NOT NULL "
                f"AND o.ship_date <= o.order_date + INTERVAL '{ON_TIME_LEAD_DAYS} days' "
                "THEN 1 ELSE 0 END) * 1.0 "
                "/ NULLIF(SUM(CASE WHEN o.status != 'cancelled' THEN 1 ELSE 0 END), 0)"
            ),
            grain_columns={
                "account": "o.account_id",
                "region": "ra.region",
                "month": "date_trunc('month', o.order_date)",
            },
            filter_columns={
                "region": "ra.region",
                "tier": "ra.tier",
                "account_id": "o.account_id",
            },
        ),
        "delamination_claim_rate": MetricQuerySpec(
            from_clause=(
                "decks d "
                "JOIN production_batches b ON d.batch_id = b.batch_id "
                "LEFT JOIN (SELECT deck_id FROM warranty_claims WHERE defect_type = 'delamination') "
                "wc ON wc.deck_id = d.deck_id"
            ),
            aggregate_expr="COUNT(wc.deck_id) * 100.0 / NULLIF(COUNT(*), 0)",
            grain_columns={
                "batch": "d.batch_id",
                "press_line": "b.press_line_id",
                "month": "date_trunc('month', d.produced_at)",
            },
            filter_columns={
                "series": "b.series",
                "press_line_id": "b.press_line_id",
                "batch_id": "d.batch_id",
            },
            where_extra=(
                f"d.ship_date IS NOT NULL AND "
                f"DATE '{AS_OF_DATE}' - d.ship_date >= {DELAM_MATURITY_DAYS}"
            ),
        ),
    }


METRIC_SPECS = _metric_specs()


@dataclass
class CompiledQuery:
    sql: str
    params: list


def build_metric_query(
    ontology: Ontology,
    metric_name: str,
    filters: dict[str, str] | None = None,
    grain: list[str] | None = None,
) -> CompiledQuery:
    """Compile a metric + filters + grain into parameterized SQL.

    Raises UnknownMetricError/UnknownFilterError/UnknownGrainError if the
    metric, a filter field, or a grain dimension isn't declared for this
    metric in the ontology. Filter *values* are bound as parameters; only
    ontology-declared column expressions are interpolated into the SQL text.
    """
    filters = filters or {}
    grain = grain or []

    if metric_name not in ontology.metrics:
        raise UnknownMetricError(
            f"'{metric_name}' is not a metric defined in the ontology. "
            f"Known metrics: {sorted(ontology.metrics)}"
        )
    metric = ontology.metrics[metric_name]
    if metric_name not in METRIC_SPECS:
        raise UnknownMetricError(
            f"'{metric_name}' is defined in the ontology YAML but has no "
            "corresponding MetricQuerySpec in compiler.py. A metric isn't "
            "queryable until both are added."
        )
    spec = METRIC_SPECS[metric_name]

    for filter_field in filters:
        if filter_field not in metric.allowed_filters:
            raise UnknownFilterError(
                f"'{filter_field}' is not an allowed filter for metric "
                f"'{metric_name}'. Allowed: {metric.allowed_filters}"
            )

    for dim in grain:
        if dim not in metric.grain:
            raise UnknownGrainError(
                f"'{dim}' is not an allowed grain dimension for metric "
                f"'{metric_name}'. Allowed: {metric.grain}"
            )

    select_parts = []
    group_by_parts = []
    for dim in grain:
        column_expr = spec.grain_columns[dim]
        select_parts.append(f"{column_expr} AS {dim}")
        group_by_parts.append(column_expr)
    select_parts.append(f"{spec.aggregate_expr} AS value")

    where_parts = list(filter(None, [spec.where_extra]))
    params: list = []
    for filter_field, value in filters.items():
        column_expr = spec.filter_columns[filter_field]
        where_parts.append(f"{column_expr} = ?")
        params.append(value)

    sql_parts = []
    if spec.ctes:
        sql_parts.append(spec.ctes)
    sql_parts.append(f"SELECT {', '.join(select_parts)}")
    sql_parts.append(f"FROM {spec.from_clause}")
    if where_parts:
        sql_parts.append("WHERE " + " AND ".join(where_parts))
    if group_by_parts:
        sql_parts.append(f"GROUP BY {', '.join(group_by_parts)}")

    return CompiledQuery(sql="\n".join(sql_parts), params=params)


# --- link traversal -------------------------------------------------------

LINK_TABLES: dict[str, str] = {
    "Deck": "decks",
    "ProductionBatch": "production_batches",
    "MaterialLot": "material_lots",
    "Supplier": "suppliers",
    "QualityInspection": "quality_inspections",
    "WarrantyClaim": "warranty_claims",
    "Order": "orders",
    "RetailAccount": "retail_accounts",
    "PressLine": "press_lines",
}


def build_link_traversal_query(
    ontology: Ontology,
    link_name: str,
    from_id: str,
) -> CompiledQuery:
    """Compile a query that, given the primary key value of a link's `from`
    object, returns the matching row(s) of the link's `to` object type.

    Raises UnknownLinkError if link_name is not declared in the ontology.
    """
    link = next((l for l in ontology.links if l.name == link_name), None)
    if link is None:
        raise UnknownLinkError(
            f"'{link_name}' is not a link defined in the ontology. "
            f"Known links: {[l.name for l in ontology.links]}"
        )

    from_table = LINK_TABLES[link.from_]
    to_table = LINK_TABLES[link.to]
    from_pk = ontology.object_types[link.from_].primary_key

    if link.cardinality == "many_to_many":
        sql = (
            f"SELECT to_tbl.* FROM {link.join_table} j "
            f"JOIN {from_table} from_tbl ON from_tbl.{from_pk} = j.{link.join_from_key} "
            f"JOIN {to_table} to_tbl ON to_tbl.{link.join_to_key} = j.{link.join_to_key} "
            f"WHERE from_tbl.{from_pk} = ?"
        )
    else:
        sql = (
            f"SELECT to_tbl.* FROM {from_table} from_tbl "
            f"JOIN {to_table} to_tbl ON to_tbl.{link.to_key} = from_tbl.{link.from_key} "
            f"WHERE from_tbl.{from_pk} = ?"
        )

    return CompiledQuery(sql=sql, params=[from_id])
