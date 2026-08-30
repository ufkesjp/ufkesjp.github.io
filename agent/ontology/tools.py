"""Anthropic tool schemas generated from the ontology at import time.

Every enum in these schemas — metric names, link names, object types, action
types — is read out of the loaded Ontology, not hand-typed. Add a metric,
link, or action to eval_boards.yml and list_available_metrics / get_metric /
traverse_link / propose_action expose it immediately; nothing here changes.

execute_tool() is the dispatcher the agent loop calls with a tool name and
the model's input for it. Every execution path goes through the compiler
(build_metric_query, build_link_traversal_query, build_get_object_query), so
the same "raise on anything not in the ontology" guarantee applies here.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime

from .compiler import (
    UnknownActionError,
    build_get_object_query,
    build_link_traversal_query,
    build_metric_query,
)
from .compiler import LINK_TABLES, ensure_actions_table
from .schema import Ontology, load_ontology

_ontology = load_ontology()  # used only to build enum lists below at import time


def _json_safe(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _rows_as_dicts(con, sql: str, params: list) -> list[dict]:
    cursor = con.execute(sql, params)
    columns = [d[0] for d in cursor.description]
    return [
        {col: _json_safe(v) for col, v in zip(columns, row)}
        for row in cursor.fetchall()
    ]


# --- tool schema generation --------------------------------------------------


def _build_tool_schemas(ontology: Ontology) -> list[dict]:
    metric_names = sorted(ontology.metrics)
    link_names = sorted(link.name for link in ontology.links)
    object_type_names = sorted(ontology.object_types)
    action_names = sorted(ontology.actions)

    return [
        {
            "name": "list_available_metrics",
            "description": (
                "List every metric the agent is allowed to compute, with its "
                "definition, grain, allowed filters, and owner. Call this "
                "first when unsure what is measurable."
            ),
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "get_metric",
            "description": (
                "Compute one metric, optionally filtered and grouped. "
                "Returns the metric's full definition and rationale "
                "alongside the result rows, so the definition can be cited."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "metric_name": {"type": "string", "enum": metric_names},
                    "filters": {
                        "type": "object",
                        "description": (
                            "field -> value. Allowed fields depend on "
                            "metric_name; see list_available_metrics."
                        ),
                        "additionalProperties": {"type": "string"},
                    },
                    "grain": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Grouping dimensions. Allowed values depend on "
                            "metric_name; see list_available_metrics."
                        ),
                    },
                },
                "required": ["metric_name"],
            },
        },
        {
            "name": "compare_periods",
            "description": (
                "Compare a metric's monthly average between two date "
                "ranges. Each period's value is the unweighted mean of its "
                "monthly readings, not a re-aggregation over raw rows. Only "
                "works for metrics with a 'month' grain dimension."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "metric_name": {"type": "string", "enum": metric_names},
                    "period_a": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "string", "description": "YYYY-MM-DD"},
                            "end": {"type": "string", "description": "YYYY-MM-DD"},
                        },
                        "required": ["start", "end"],
                    },
                    "period_b": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "string", "description": "YYYY-MM-DD"},
                            "end": {"type": "string", "description": "YYYY-MM-DD"},
                        },
                        "required": ["start", "end"],
                    },
                    "filters": {
                        "type": "object",
                        "description": (
                            "field -> value. Allowed fields depend on "
                            "metric_name; see list_available_metrics."
                        ),
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["metric_name", "period_a", "period_b"],
            },
        },
        {
            "name": "get_object",
            "description": "Fetch one object by its primary key.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "object_type": {"type": "string", "enum": object_type_names},
                    "object_id": {"type": "string"},
                },
                "required": ["object_type", "object_id"],
            },
        },
        {
            "name": "traverse_link",
            "description": (
                "Follow a named ontology link from one object's id to the "
                "related object(s). This is the only way to move between "
                "object types (e.g. from a batch to the material lots it "
                "consumed, or a lot to its supplier) — metric filters "
                "cannot substitute for it."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "link_name": {"type": "string", "enum": link_names},
                    "from_id": {
                        "type": "string",
                        "description": "Primary key value of the link's `from` object.",
                    },
                },
                "required": ["link_name", "from_id"],
            },
        },
        {
            "name": "propose_action",
            "description": (
                "Propose one of the ontology's defined actions. Evaluates "
                "preconditions and, if they pass, writes a pending_approval "
                "row to the actions table — it never applies the action "
                "itself or mutates warehouse data. A human must approve it "
                "separately (runtime.approve) before it changes what any "
                "tool sees."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "action_type": {"type": "string", "enum": action_names},
                    "parameters": {
                        "type": "object",
                        "description": (
                            "field -> value. Required fields depend on "
                            "action_type; see the ontology's action "
                            "parameter lists."
                        ),
                        "additionalProperties": {"type": "string"},
                    },
                    "evidence": {
                        "type": "string",
                        "description": (
                            "The specific metric reading, claim, or "
                            "lot/batch reference that justifies this action."
                        ),
                    },
                },
                "required": ["action_type", "parameters", "evidence"],
            },
        },
    ]


TOOL_SCHEMAS = _build_tool_schemas(_ontology)


# --- tool execution -----------------------------------------------------


def _list_available_metrics(ontology: Ontology) -> dict:
    return {
        "metrics": [
            {
                "name": name,
                "definition": metric.definition,
                "grain": metric.grain,
                "allowed_filters": metric.allowed_filters,
                "owner": metric.owner,
            }
            for name, metric in sorted(ontology.metrics.items())
        ]
    }


def _get_metric(
    ontology: Ontology,
    con,
    metric_name: str,
    filters: dict | None,
    grain: list[str] | None,
) -> dict:
    query = build_metric_query(ontology, metric_name, filters=filters, grain=grain, con=con)
    metric = ontology.metrics[metric_name]
    rows = _rows_as_dicts(con, query.sql, query.params)
    return {
        "metric": metric_name,
        "definition": metric.definition,
        "rationale": metric.rationale,
        "grain": grain or [],
        "filters": filters or {},
        "rows": rows,
        "excluded_batches": query.excluded_batch_ids,
        "excluded_reason": (
            "held out of this result because each has an approved "
            "quarantine_batch action"
            if query.excluded_batch_ids
            else None
        ),
    }


def _compare_periods(
    ontology: Ontology,
    con,
    metric_name: str,
    period_a: dict,
    period_b: dict,
    filters: dict | None,
) -> dict:
    metric = ontology.metrics.get(metric_name)
    if metric is None:
        from .compiler import UnknownMetricError

        raise UnknownMetricError(
            f"'{metric_name}' is not a metric defined in the ontology. "
            f"Known metrics: {sorted(ontology.metrics)}"
        )
    if "month" not in metric.grain:
        from .compiler import UnknownGrainError

        raise UnknownGrainError(
            f"'{metric_name}' has no 'month' grain dimension, so "
            f"compare_periods cannot bucket it by period. "
            f"Allowed grain: {metric.grain}"
        )

    query = build_metric_query(ontology, metric_name, filters=filters, grain=["month"], con=con)
    rows = _rows_as_dicts(con, query.sql, query.params)

    def _in_range(month_str: str, start: date, end: date) -> bool:
        month_date = date.fromisoformat(month_str[:10])
        return start <= month_date <= end

    def _aggregate(period: dict) -> float | None:
        start = date.fromisoformat(period["start"])
        end = date.fromisoformat(period["end"])
        values = [
            row["value"]
            for row in rows
            if row["value"] is not None and _in_range(row["month"], start, end)
        ]
        return sum(values) / len(values) if values else None

    value_a = _aggregate(period_a)
    value_b = _aggregate(period_b)
    delta = value_b - value_a if value_a is not None and value_b is not None else None
    pct_change = delta / value_a * 100 if delta is not None and value_a else None

    return {
        "metric": metric_name,
        "definition": metric.definition,
        "period_a": period_a,
        "value_a": value_a,
        "period_b": period_b,
        "value_b": value_b,
        "delta": delta,
        "pct_change": pct_change,
        "note": (
            "each period's value is the unweighted mean of its monthly "
            "metric readings"
        ),
        "excluded_batches": query.excluded_batch_ids,
    }


def _get_object(ontology: Ontology, con, object_type: str, object_id: str) -> dict:
    query = build_get_object_query(ontology, object_type, object_id)
    rows = _rows_as_dicts(con, query.sql, query.params)
    return {
        "object_type": object_type,
        "object_id": object_id,
        "found": bool(rows),
        "object": rows[0] if rows else None,
    }


def _traverse_link(ontology: Ontology, con, link_name: str, from_id: str) -> dict:
    query = build_link_traversal_query(ontology, link_name, from_id)
    rows = _rows_as_dicts(con, query.sql, query.params)
    return {"link": link_name, "from_id": from_id, "rows": rows, "count": len(rows)}


_COMPARISON_OPS = {
    "equals": lambda actual, expected: actual == expected,
    "not_equals": lambda actual, expected: actual != expected,
    "gt": lambda actual, expected: actual > expected,
    "gte": lambda actual, expected: actual >= expected,
    "lt": lambda actual, expected: actual < expected,
    "lte": lambda actual, expected: actual <= expected,
}


def _coerce_like(value: str, reference):
    if isinstance(reference, bool) or reference is None:
        return value
    if isinstance(reference, (int, float)):
        try:
            return type(reference)(value)
        except (TypeError, ValueError):
            return value
    return value


def _propose_action(
    ontology: Ontology, con, action_type: str, parameters: dict | None, evidence: str
) -> dict:
    parameters = parameters or {}

    if action_type not in ontology.actions:
        raise UnknownActionError(
            f"'{action_type}' is not an action defined in the ontology. "
            f"Known actions: {sorted(ontology.actions)}"
        )
    action = ontology.actions[action_type]

    missing_params = [name for name in action.parameters if name not in parameters]
    if missing_params:
        return {
            "status": "rejected",
            "reason": f"missing required parameters: {missing_params}",
        }

    if not evidence or not evidence.strip():
        return {
            "status": "rejected",
            "reason": (
                "no evidence provided. required_evidence for this action: "
                f"{action.required_evidence}"
            ),
        }

    target_type = action.target_object_type
    target_primary_key = ontology.object_types[target_type].primary_key
    if target_primary_key not in parameters:
        return {
            "status": "rejected",
            "reason": (
                f"parameters must include '{target_primary_key}' to "
                f"identify the target {target_type}"
            ),
        }
    target_id = parameters[target_primary_key]

    table = LINK_TABLES[target_type]
    cursor = con.execute(f"SELECT * FROM {table} WHERE {target_primary_key} = ?", [target_id])
    row = cursor.fetchone()
    if row is None:
        return {
            "status": "rejected",
            "reason": f"no {target_type} found with {target_primary_key} = {target_id!r}",
        }
    columns = [d[0] for d in cursor.description]
    record = dict(zip(columns, row))

    for precondition in action.preconditions:
        actual = record.get(precondition.field)
        expected = _coerce_like(precondition.value, actual)
        comparison = _COMPARISON_OPS[precondition.op]
        if actual is None or not comparison(actual, expected):
            return {
                "status": "precondition_failed",
                "reason": precondition.description,
                "field": precondition.field,
                "actual_value": _json_safe(actual),
            }

    ensure_actions_table(con)
    action_id = f"ACT-{uuid.uuid4().hex[:10]}"
    created_at = datetime.utcnow()
    con.execute(
        "INSERT INTO actions "
        "(action_id, action_type, target_object_type, target_id, parameters, "
        " evidence, status, created_at, approved_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'pending_approval', ?, NULL)",
        [
            action_id,
            action_type,
            target_type,
            str(target_id),
            json.dumps(parameters, default=str),
            evidence,
            created_at,
        ],
    )
    return {
        "status": "pending_approval",
        "action_id": action_id,
        "action_type": action_type,
        "target_object_type": target_type,
        "target_id": target_id,
        "parameters": parameters,
        "evidence": evidence,
    }


def execute_tool(name: str, tool_input: dict, *, ontology: Ontology, con) -> dict:
    """Dispatch one Anthropic tool call to its ontology-backed implementation."""
    if name == "list_available_metrics":
        return _list_available_metrics(ontology)
    if name == "get_metric":
        return _get_metric(
            ontology, con, tool_input["metric_name"], tool_input.get("filters"), tool_input.get("grain")
        )
    if name == "compare_periods":
        return _compare_periods(
            ontology,
            con,
            tool_input["metric_name"],
            tool_input["period_a"],
            tool_input["period_b"],
            tool_input.get("filters"),
        )
    if name == "get_object":
        return _get_object(ontology, con, tool_input["object_type"], tool_input["object_id"])
    if name == "traverse_link":
        return _traverse_link(ontology, con, tool_input["link_name"], tool_input["from_id"])
    if name == "propose_action":
        return _propose_action(
            ontology,
            con,
            tool_input["action_type"],
            tool_input.get("parameters"),
            tool_input.get("evidence", ""),
        )
    raise ValueError(f"unknown tool '{name}'")
