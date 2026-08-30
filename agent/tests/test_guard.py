"""Tests for runtime/guard.py against a fake Anthropic client — no real API
calls in the pytest suite, so `uv run pytest` never touches the API budget."""

from types import SimpleNamespace

from runtime.guard import check_coverage


class _FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, input_):
        self.input = input_


class _FakeMessages:
    def __init__(self, decision: dict):
        self._decision = decision
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(content=[_FakeToolUseBlock(self._decision)])


class _FakeClient:
    def __init__(self, decision: dict):
        self.messages = _FakeMessages(decision)


def test_in_scope_question_is_not_refused(ontology):
    client = _FakeClient(
        {
            "in_scope": True,
            "ambiguous": False,
            "reason": "asks about a declared metric",
            "nearest_metrics": ["delamination_claim_rate"],
            "clarifying_question": None,
        }
    )
    decision = check_coverage("What's the delamination claim rate?", ontology, client=client)
    assert decision.in_scope is True
    assert decision.ambiguous is False


def test_out_of_scope_question_is_refused(ontology):
    client = _FakeClient(
        {
            "in_scope": False,
            "ambiguous": False,
            "reason": "customer satisfaction survey data isn't in this ontology",
            "nearest_metrics": [],
            "clarifying_question": None,
        }
    )
    decision = check_coverage("What's our NPS score?", ontology, client=client)
    assert decision.in_scope is False
    assert decision.nearest_metrics == []


def test_prompt_lists_declared_metrics(ontology):
    client = _FakeClient(
        {"in_scope": True, "ambiguous": False, "reason": "x", "nearest_metrics": []}
    )
    check_coverage("anything", ontology, client=client)
    system_prompt = client.messages.last_kwargs["system"]
    for metric_name in ontology.metrics:
        assert metric_name in system_prompt
