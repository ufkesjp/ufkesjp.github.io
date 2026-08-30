"""Tests for agent/ontology/tools.py: schema generation and execution for
all six tools, and the closed loop (propose -> approve -> compiler honors
it) that's the point of Run 2."""

import pytest

from ontology.compiler import approved_quarantined_batch_ids, build_metric_query
from ontology.tools import TOOL_SCHEMAS, execute_tool
from runtime.approve import approve


def test_tool_schemas_cover_all_six_tools():
    names = {tool["name"] for tool in TOOL_SCHEMAS}
    assert names == {
        "list_available_metrics",
        "get_metric",
        "compare_periods",
        "get_object",
        "traverse_link",
        "propose_action",
    }


def test_metric_name_enum_matches_ontology(ontology):
    get_metric = next(t for t in TOOL_SCHEMAS if t["name"] == "get_metric")
    assert set(get_metric["input_schema"]["properties"]["metric_name"]["enum"]) == set(
        ontology.metrics
    )


def test_list_available_metrics(ontology, db_connection):
    result = execute_tool("list_available_metrics", {}, ontology=ontology, con=db_connection)
    names = {m["name"] for m in result["metrics"]}
    assert names == set(ontology.metrics)


def test_get_metric_includes_definition_for_citation(ontology, db_connection):
    result = execute_tool(
        "get_metric",
        {"metric_name": "delamination_claim_rate", "grain": ["batch"]},
        ontology=ontology,
        con=db_connection,
    )
    assert result["definition"] == ontology.metrics["delamination_claim_rate"].definition
    assert result["rows"]


def test_get_metric_unknown_filter_raises(ontology, db_connection):
    with pytest.raises(Exception):
        execute_tool(
            "get_metric",
            {"metric_name": "delamination_claim_rate", "filters": {"nope": "x"}},
            ontology=ontology,
            con=db_connection,
        )


def test_compare_periods(ontology, db_connection):
    result = execute_tool(
        "compare_periods",
        {
            "metric_name": "on_time_ship_rate",
            "period_a": {"start": "2025-01-01", "end": "2025-03-31"},
            "period_b": {"start": "2025-06-01", "end": "2025-08-31"},
        },
        ontology=ontology,
        con=db_connection,
    )
    assert "delta" in result
    assert result["definition"] == ontology.metrics["on_time_ship_rate"].definition


def test_get_object_found_and_not_found(ontology, db_connection):
    found = execute_tool(
        "get_object", {"object_type": "ProductionBatch", "object_id": "B0240"}, ontology=ontology, con=db_connection
    )
    assert found["found"] is True
    assert found["object"]["batch_id"] == "B0240"

    missing = execute_tool(
        "get_object",
        {"object_type": "ProductionBatch", "object_id": "NOPE"},
        ontology=ontology,
        con=db_connection,
    )
    assert missing["found"] is False


def test_traverse_link(ontology, db_connection):
    result = execute_tool(
        "traverse_link", {"link_name": "supplied_by", "from_id": "LOT-MAP-001"}, ontology=ontology, con=db_connection
    )
    assert result["count"] == 1
    assert result["rows"][0]["supplier_id"]


def test_propose_action_precondition_failure(ontology, write_db_connection):
    result = execute_tool(
        "propose_action",
        {
            "action_type": "reroute_order",
            "parameters": {
                "order_id": "ORD00001",
                "new_batch_id": "B0070",
                "reason": "test",
            },
            "evidence": "order's fulfilling batch is quarantined",
        },
        ontology=ontology,
        con=write_db_connection,
    )
    # ORD00001 is already 'shipped', so the "must still be pending"
    # precondition fails and the tool must return the reason, not raise.
    assert result["status"] == "precondition_failed"
    assert result["field"] == "status"


def test_propose_action_missing_evidence_is_rejected(ontology, write_db_connection):
    result = execute_tool(
        "propose_action",
        {
            "action_type": "quarantine_batch",
            "parameters": {"batch_id": "B0240", "reason": "test"},
            "evidence": "",
        },
        ontology=ontology,
        con=write_db_connection,
    )
    assert result["status"] == "rejected"


def test_quarantine_closes_the_loop(ontology, tmp_path, monkeypatch):
    """propose -> approve -> the compiler excludes the batch. This is the
    part of Run 2 that makes it an agent rather than a proposal formatter."""
    import shutil

    import duckdb

    from data.seed import DB_PATH

    tmp_db = tmp_path / "loop_test.duckdb"
    shutil.copy(DB_PATH, tmp_db)

    con = duckdb.connect(str(tmp_db))
    before = build_metric_query(ontology, "delamination_claim_rate", grain=["batch"], con=con)
    before_batches = {row[0] for row in con.execute(before.sql, before.params).fetchall()}
    assert "B0240" in before_batches

    proposal = execute_tool(
        "propose_action",
        {
            "action_type": "quarantine_batch",
            "parameters": {"batch_id": "B0240", "reason": "elevated delamination claims"},
            "evidence": "delamination_claim_rate reading of 6.0 per 100 decks on B0240",
        },
        ontology=ontology,
        con=con,
    )
    assert proposal["status"] == "pending_approval"
    action_id = proposal["action_id"]
    # The copied db may already carry approved quarantines from real
    # recorded traces (Run 2 commits actions into the real eval_boards.duckdb) —
    # assert relative to that baseline, not that the table starts empty.
    already_quarantined = set(approved_quarantined_batch_ids(con))
    assert "B0240" not in already_quarantined
    con.close()  # approve() opens its own connection; duckdb allows one writer at a time

    # approve() connects to DB_PATH by default; point it at our throwaway
    # copy so this test exercises the real approval CLI logic without
    # touching the committed db.
    monkeypatch.setattr("runtime.approve.DB_PATH", tmp_db)
    approved_id = approve(action_id)
    assert approved_id == action_id

    con = duckdb.connect(str(tmp_db))
    assert set(approved_quarantined_batch_ids(con)) == already_quarantined | {"B0240"}

    after = build_metric_query(ontology, "delamination_claim_rate", grain=["batch"], con=con)
    after_batches = {row[0] for row in con.execute(after.sql, after.params).fetchall()}
    assert "B0240" not in after_batches
    assert set(after.excluded_batch_ids) == already_quarantined | {"B0240"}
    con.close()
