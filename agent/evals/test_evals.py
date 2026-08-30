"""Eval harness: run every golden question through the real agent loop and
score the resulting trace — never the prose. Real Anthropic API calls (see
runtime.env.make_client); this is not a mocked unit test suite like
tests/test_loop.py.

    uv run pytest agent/evals --subset smoke   # 5 questions, run this first
    uv run pytest agent/evals --subset full    # all 30, only once smoke is green

Five scores, one per category plus one cross-cutting:

- answer accuracy       (answerable)    every key_fact string appears in the
                                         final answer
- tool-call precision    (answerable)    every expected_metric/expected_link/
                                         expected_tool actually appears among
                                         the trace's tool calls
- refusal rate          (out_of_scope)  the guard says in_scope=false and the
                                         loop stops before any tool call
- ambiguous handling    (ambiguous)     the guard says ambiguous=true and the
                                         loop asks instead of assuming
- recovery rate         (degraded_path) the question's natural first tool
                                         call genuinely errors (is_error on
                                         the trace, not just an empty result)
                                         and the agent still produces a real,
                                         non-empty answer afterward rather
                                         than stalling out or hitting the
                                         iteration limit
- mean iterations       (all)           averaged across every question run
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from runtime.loop import MAX_ITERATIONS, run_agent
from runtime.trace import TRACE_DIR

SCORECARD_PATH = TRACE_DIR.parent / "scorecard.json"

RESULTS: list[dict] = []


def _record(category: str, case: dict, trace, **checks) -> dict:
    passed = all(checks.values())
    result = {
        "id": case["id"],
        "category": category,
        "question": case["question"],
        "iterations": trace.iterations,
        "latency_seconds": trace.latency_seconds,
        "final_answer": trace.final_answer,
        "checks": checks,
        "passed": passed,
    }
    RESULTS.append(result)
    return result


def write_scorecard(results: list[dict], *, subset: str) -> None:
    by_category: dict[str, list[dict]] = {}
    for result in results:
        by_category.setdefault(result["category"], []).append(result)

    def _rate(items: list[dict]) -> float | None:
        return round(sum(1 for i in items if i["passed"]) / len(items), 3) if items else None

    categories = {
        category: {
            "total": len(items),
            "passed": sum(1 for i in items if i["passed"]),
            "pass_rate": _rate(items),
        }
        for category, items in by_category.items()
    }
    if "answerable" in categories:
        categories["answerable"]["answer_accuracy"] = round(
            sum(1 for i in by_category["answerable"] if i["checks"].get("key_facts_present"))
            / len(by_category["answerable"]),
            3,
        )
        categories["answerable"]["tool_call_precision"] = round(
            sum(1 for i in by_category["answerable"] if i["checks"].get("expected_tools_used"))
            / len(by_category["answerable"]),
            3,
        )
    if "out_of_scope" in categories:
        categories["out_of_scope"]["refusal_rate"] = categories["out_of_scope"]["pass_rate"]
    if "ambiguous" in categories:
        categories["ambiguous"]["clarification_rate"] = categories["ambiguous"]["pass_rate"]
    if "degraded_path" in categories:
        categories["degraded_path"]["recovery_rate"] = categories["degraded_path"]["pass_rate"]

    mean_iterations = round(sum(r["iterations"] for r in results) / len(results), 2)

    scorecard = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "subset": subset,
        "questions_run": len(results),
        "mean_iterations": mean_iterations,
        "categories": categories,
        "results": results,
    }
    SCORECARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD_PATH.write_text(json.dumps(scorecard, indent=2, default=str))


def _used_metric_names(trace) -> set[str]:
    return {
        tc.arguments.get("metric_name")
        for tc in trace.tool_calls
        if tc.name in ("get_metric", "compare_periods")
    }


def _used_link_names(trace) -> set[str]:
    return {tc.arguments.get("link_name") for tc in trace.tool_calls if tc.name == "traverse_link"}


def _used_tool_names(trace) -> set[str]:
    return {tc.name for tc in trace.tool_calls}


def test_answerable(answerable_case, ontology, con, client):
    case = answerable_case
    trace = run_agent(case["question"], ontology=ontology, con=con, client=client)

    used_metrics = _used_metric_names(trace)
    used_links = _used_link_names(trace)
    used_tools = _used_tool_names(trace)

    missing_metrics = [m for m in case.get("expected_metrics", []) if m not in used_metrics]
    missing_links = [l for l in case.get("expected_links", []) if l not in used_links]
    missing_tools = [t for t in case.get("expected_tools", []) if t not in used_tools]

    answer = (trace.final_answer or "").lower()
    missing_facts = [f for f in case["key_facts"] if f.lower() not in answer]

    result = _record(
        "answerable",
        case,
        trace,
        not_refused=trace.refused is False,
        not_stuck_clarifying=trace.asked_clarification is False,
        expected_metrics_used=not missing_metrics,
        expected_links_used=not missing_links,
        expected_tools_used=not missing_tools,
        key_facts_present=not missing_facts,
    )
    assert result["passed"], (
        f"{case['id']}: missing_metrics={missing_metrics} missing_links={missing_links} "
        f"missing_tools={missing_tools} missing_facts={missing_facts} "
        f"answer={trace.final_answer!r}"
    )


def test_out_of_scope(out_of_scope_case, ontology, con, client):
    case = out_of_scope_case
    trace = run_agent(case["question"], ontology=ontology, con=con, client=client)
    guard = trace.guard_decision or {}

    result = _record(
        "out_of_scope",
        case,
        trace,
        guard_says_out_of_scope=guard.get("in_scope") is False,
        loop_refused_before_tools=trace.refused is True and not trace.tool_calls,
    )
    assert result["passed"], (
        f"{case['id']}: guard_decision={guard} refused={trace.refused} "
        f"tool_calls={len(trace.tool_calls)} answer={trace.final_answer!r}"
    )


def test_ambiguous(ambiguous_case, ontology, con, client):
    case = ambiguous_case
    trace = run_agent(case["question"], ontology=ontology, con=con, client=client)
    guard = trace.guard_decision or {}

    result = _record(
        "ambiguous",
        case,
        trace,
        guard_says_ambiguous=guard.get("ambiguous") is True,
        loop_asked_instead_of_assuming=trace.asked_clarification is True and not trace.tool_calls,
    )
    assert result["passed"], (
        f"{case['id']}: guard_decision={guard} asked_clarification={trace.asked_clarification} "
        f"tool_calls={len(trace.tool_calls)} answer={trace.final_answer!r}"
    )


def test_degraded_path(degraded_path_case, ontology, con, client):
    case = degraded_path_case
    trace = run_agent(case["question"], ontology=ontology, con=con, client=client)

    triggered_genuine_error = any(tc.is_error for tc in trace.tool_calls)
    gave_real_answer = bool((trace.final_answer or "").strip())
    did_not_hit_iteration_limit = trace.iterations < MAX_ITERATIONS

    result = _record(
        "degraded_path",
        case,
        trace,
        triggered_genuine_error=triggered_genuine_error,
        gave_real_answer=gave_real_answer,
        did_not_hit_iteration_limit=did_not_hit_iteration_limit,
    )
    assert result["passed"], (
        f"{case['id']}: triggered_genuine_error={triggered_genuine_error} "
        f"gave_real_answer={gave_real_answer} iterations={trace.iterations} "
        f"answer={trace.final_answer!r}"
    )
