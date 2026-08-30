"""Tests for agent/ontology/compiler.py: every metric must compile and
execute against the real seeded warehouse, and every kind of out-of-ontology
request (unknown metric, filter, grain, or link) must raise before any SQL
touches the database."""

import pytest

from ontology.compiler import (
    UnknownFilterError,
    UnknownGrainError,
    UnknownLinkError,
    UnknownMetricError,
    build_link_traversal_query,
    build_metric_query,
)


@pytest.mark.parametrize("metric_name", [
    "first_pass_yield",
    "scrap_cost_per_batch",
    "veneer_yield",
    "on_time_ship_rate",
    "delamination_claim_rate",
])
def test_every_metric_compiles_and_executes(ontology, db_connection, metric_name):
    metric = ontology.metrics[metric_name]
    query = build_metric_query(ontology, metric_name, filters={}, grain=metric.grain[:1])
    rows = db_connection.execute(query.sql, query.params).fetchall()
    assert len(rows) > 0


def test_metric_query_with_filter_and_multiple_grain_dims(ontology, db_connection):
    query = build_metric_query(
        ontology,
        "delamination_claim_rate",
        filters={"series": "Pro"},
        grain=["batch", "press_line"],
    )
    rows = db_connection.execute(query.sql, query.params).fetchall()
    assert len(rows) > 0
    assert query.params == ["Pro"]


def test_unknown_metric_raises_before_touching_sql(ontology):
    with pytest.raises(UnknownMetricError):
        build_metric_query(ontology, "revenue_per_click")


def test_unknown_filter_raises(ontology):
    with pytest.raises(UnknownFilterError):
        build_metric_query(ontology, "delamination_claim_rate", filters={"nonsense": "x"})


def test_unknown_grain_dimension_raises(ontology):
    with pytest.raises(UnknownGrainError):
        build_metric_query(ontology, "delamination_claim_rate", grain=["supplier"])


def test_filter_values_are_bound_not_interpolated(ontology):
    malicious = "x'; DROP TABLE decks; --"
    query = build_metric_query(
        ontology, "delamination_claim_rate", filters={"series": malicious}
    )
    assert malicious not in query.sql
    assert query.params == [malicious]


def test_veneer_yield_is_a_fraction_between_0_and_1(ontology, db_connection):
    query = build_metric_query(ontology, "veneer_yield", grain=["lot"])
    rows = db_connection.execute(query.sql, query.params).fetchall()
    for _lot_id, value in rows:
        assert 0.0 <= value <= 1.0


def test_consumes_link_traversal_returns_material_lots(ontology, db_connection):
    query = build_link_traversal_query(ontology, "consumes", "B0001")
    rows = db_connection.execute(query.sql, query.params).fetchall()
    assert len(rows) >= 1


def test_many_to_one_link_traversal_produced_by(ontology, db_connection):
    deck_id = db_connection.execute("SELECT deck_id FROM decks LIMIT 1").fetchone()[0]
    query = build_link_traversal_query(ontology, "produced_by", deck_id)
    rows = db_connection.execute(query.sql, query.params).fetchall()
    assert len(rows) == 1


def test_unknown_link_raises(ontology):
    with pytest.raises(UnknownLinkError):
        build_link_traversal_query(ontology, "not_a_real_link", "X1")


def test_delamination_claim_rate_surfaces_the_planted_signal(ontology, db_connection):
    """The batch-grain query, with no hints, should rank at least some of
    the twelve suspect batches near the top by claim rate."""
    query = build_metric_query(ontology, "delamination_claim_rate", grain=["batch"])
    rows = db_connection.execute(query.sql, query.params).fetchall()
    rows.sort(key=lambda r: (r[1] is None, -(r[1] or 0)))
    top_20_batches = {r[0] for r in rows[:20]}

    suspect_batches = {
        r[0] for r in db_connection.execute("""
            SELECT batch_id FROM (
                SELECT batch_id, lot_id FROM batch_material_lots
            ) bml
            JOIN (
                SELECT lot_id FROM (
                    SELECT lot_id, COUNT(DISTINCT batch_id) AS n
                    FROM batch_material_lots GROUP BY lot_id
                ) WHERE n = 12
            ) suspect USING (lot_id)
        """).fetchall()
    }
    assert len(top_20_batches & suspect_batches) >= 3
