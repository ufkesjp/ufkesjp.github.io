"""Tests for runtime/loop.py against a fake Anthropic client — no real API
calls, so the pytest suite never touches the API budget. The fake client
distinguishes the guard's tool-forced call (by seeing "guard_decision" among
the offered tools) from ordinary loop turns."""

from types import SimpleNamespace

from runtime.loop import run_agent

_USAGE = SimpleNamespace(input_tokens=10, output_tokens=5)


class _TextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _ToolUseBlock:
    type = "tool_use"

    def __init__(self, id_, name, input_):
        self.id = id_
        self.name = name
        self.input = input_


class _FakeClient:
    def __init__(self, guard_decision: dict, loop_responses: list):
        self._guard_decision = guard_decision
        self._loop_responses = list(loop_responses)
        self.calls: list[dict] = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        tools = kwargs.get("tools") or []
        if any(t.get("name") == "guard_decision" for t in tools):
            return SimpleNamespace(
                content=[_ToolUseBlock("guard-call", "guard_decision", self._guard_decision)],
                usage=_USAGE,
            )
        return self._loop_responses.pop(0)


def _in_scope_decision(**overrides):
    decision = {
        "in_scope": True,
        "ambiguous": False,
        "reason": "asks about a declared metric",
        "nearest_metrics": [],
        "clarifying_question": None,
    }
    decision.update(overrides)
    return decision


def test_happy_path_one_tool_call_then_answer(ontology, db_connection):
    responses = [
        SimpleNamespace(
            content=[_ToolUseBlock("t1", "list_available_metrics", {})], usage=_USAGE
        ),
        SimpleNamespace(content=[_TextBlock("Here are the metrics.")], usage=_USAGE),
    ]
    client = _FakeClient(_in_scope_decision(), responses)

    trace = run_agent(
        "what metrics are available?", ontology=ontology, con=db_connection, client=client
    )

    assert trace.refused is False
    assert trace.asked_clarification is False
    assert trace.iterations == 2
    assert len(trace.tool_calls) == 1
    assert trace.tool_calls[0].name == "list_available_metrics"
    assert trace.tool_calls[0].is_error is False
    assert trace.final_answer == "Here are the metrics."


def test_out_of_scope_question_is_refused_before_any_tool_call(ontology, db_connection):
    decision = _in_scope_decision(
        in_scope=False, reason="not covered", nearest_metrics=["first_pass_yield"]
    )
    client = _FakeClient(decision, loop_responses=[])

    trace = run_agent("what's the weather?", ontology=ontology, con=db_connection, client=client)

    assert trace.refused is True
    assert trace.tool_calls == []
    assert "first_pass_yield" in trace.final_answer
    # only the guard call happened, never a loop turn
    assert len(client.calls) == 1


def test_ambiguous_question_asks_for_clarification(ontology, db_connection):
    decision = _in_scope_decision(
        ambiguous=True, clarifying_question="Which series do you mean?"
    )
    client = _FakeClient(decision, loop_responses=[])

    trace = run_agent("is it up?", ontology=ontology, con=db_connection, client=client)

    assert trace.asked_clarification is True
    assert trace.final_answer == "Which series do you mean?"
    assert trace.tool_calls == []


def test_recovers_after_an_empty_tool_result(ontology, db_connection):
    """A get_object for an id that doesn't exist comes back empty, not an
    error; the trace must record it as empty so eval scoring can check the
    agent revised its approach on the next turn instead of fabricating."""
    responses = [
        SimpleNamespace(
            content=[
                _ToolUseBlock(
                    "t1", "get_object", {"object_type": "ProductionBatch", "object_id": "NOPE"}
                )
            ],
            usage=_USAGE,
        ),
        SimpleNamespace(
            content=[
                _ToolUseBlock(
                    "t2", "get_object", {"object_type": "ProductionBatch", "object_id": "B0240"}
                )
            ],
            usage=_USAGE,
        ),
        SimpleNamespace(content=[_TextBlock("Found it on the second try.")], usage=_USAGE),
    ]
    client = _FakeClient(_in_scope_decision(), responses)

    trace = run_agent(
        "look up batch NOPE", ontology=ontology, con=db_connection, client=client
    )

    assert len(trace.tool_calls) == 2
    assert trace.tool_calls[0].is_empty is True
    assert trace.tool_calls[0].is_error is False
    assert trace.tool_calls[1].is_empty is False
    assert trace.final_answer == "Found it on the second try."


def test_unknown_tool_input_is_reported_as_error_not_raised(ontology, db_connection):
    responses = [
        SimpleNamespace(
            content=[
                _ToolUseBlock(
                    "t1", "get_metric", {"metric_name": "delamination_claim_rate", "filters": {"nope": "x"}}
                )
            ],
            usage=_USAGE,
        ),
        SimpleNamespace(content=[_TextBlock("That filter isn't valid.")], usage=_USAGE),
    ]
    client = _FakeClient(_in_scope_decision(), responses)

    trace = run_agent("bad filter", ontology=ontology, con=db_connection, client=client)

    assert trace.tool_calls[0].is_error is True
    assert "error" in trace.tool_calls[0].result
    assert trace.final_answer == "That filter isn't valid."
