"""Coverage guard: decides whether the ontology can answer a question at
all, before the agent loop spends a single tool call on it.

This is deliberately its own model call rather than something folded into
the agent loop's system prompt. The loop's model has every incentive to be
helpful and stretch toward an answer; a separate call, given nothing but the
ontology's declared surface area, has no conversation to be helpful in and
nothing to lose by refusing. That separation is the hard boundary — not the
agent's own judgment about whether it's in scope.
"""

from __future__ import annotations

from dataclasses import dataclass

import anthropic

from ontology.schema import Ontology
from runtime.env import make_client

GUARD_MODEL = "claude-haiku-4-5-20251001"

_GUARD_TOOL = {
    "name": "guard_decision",
    "description": "Decide whether the ontology below can answer the question.",
    "input_schema": {
        "type": "object",
        "properties": {
            "in_scope": {
                "type": "boolean",
                "description": "True if the question can be answered using only the metrics, links, and objects listed.",
            },
            "ambiguous": {
                "type": "boolean",
                "description": (
                    "True only if in_scope is true AND there is no reasonable "
                    "default reading — e.g. the question could equally mean two "
                    "different declared metrics, or names an object/segment "
                    "that doesn't disambiguate to one real entity. An "
                    "open-ended investigative question ('X is up, what's going "
                    "on?') is NOT ambiguous merely for lacking an explicit time "
                    "window or grain — 'investigate using the most relevant "
                    "metric, most recent data, and any grouping that surfaces a "
                    "pattern' is itself the reasonable default. A request to "
                    "propose an action is also NOT ambiguous merely because "
                    "you'd want to double-check the ids first — propose_action "
                    "never applies anything by itself (it only ever writes a "
                    "pending_approval row a human reviews separately), so that "
                    "kind of pre-action confirmation is not this guard's job. "
                    "Prefer false; only use true when a default answer would "
                    "likely be answering a different question than the one "
                    "asked."
                ),
            },
            "reason": {
                "type": "string",
                "description": "One or two sentences explaining the decision.",
            },
            "nearest_metrics": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Metric names (from the list given) most relevant to the "
                    "question, whether or not the question is in scope."
                ),
            },
            "clarifying_question": {
                "type": ["string", "null"],
                "description": "If ambiguous is true, the single question to ask back. Otherwise null.",
            },
        },
        "required": ["in_scope", "ambiguous", "reason", "nearest_metrics"],
    },
}

_SYSTEM_PROMPT_TEMPLATE = """\
You are the coverage guard for an analytics agent. You do not answer \
questions yourself. You only decide whether the question below could be \
answered using exactly this ontology — nothing more, nothing assumed:

{capabilities}

A question is in scope only if it can be answered using these metrics, \
these links, and these object types, possibly combined. If it requires a \
metric, entity, or relationship not listed, it is out of scope, even if it \
sounds related. Do not be generous — a plausible-sounding question about \
data this ontology does not track is still out of scope.
"""


def _summarize_ontology(ontology: Ontology) -> str:
    lines = ["Metrics:"]
    for name, metric in sorted(ontology.metrics.items()):
        lines.append(f"- {name}: {metric.definition.strip()}")
        lines.append(f"  grain: {metric.grain}, filters: {metric.allowed_filters}")
    lines.append("\nObject types:")
    for name, obj in sorted(ontology.object_types.items()):
        lines.append(f"- {name}: {sorted(obj.properties)}")
    lines.append("\nLinks:")
    for link in ontology.links:
        lines.append(f"- {link.name}: {link.from_} -> {link.to} ({link.cardinality})")
    lines.append("\nActions the agent may propose (not compute, propose):")
    for name in sorted(ontology.actions):
        lines.append(f"- {name}")
    return "\n".join(lines)


@dataclass
class GuardDecision:
    in_scope: bool
    ambiguous: bool
    reason: str
    nearest_metrics: list[str]
    clarifying_question: str | None = None

    def to_dict(self) -> dict:
        return {
            "in_scope": self.in_scope,
            "ambiguous": self.ambiguous,
            "reason": self.reason,
            "nearest_metrics": self.nearest_metrics,
            "clarifying_question": self.clarifying_question,
        }


def check_coverage(
    question: str,
    ontology: Ontology,
    *,
    client: anthropic.Anthropic | None = None,
    model: str = GUARD_MODEL,
) -> GuardDecision:
    client = client or make_client()
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(capabilities=_summarize_ontology(ontology))

    message = client.messages.create(
        model=model,
        max_tokens=500,
        system=system_prompt,
        tools=[_GUARD_TOOL],
        tool_choice={"type": "tool", "name": "guard_decision"},
        messages=[{"role": "user", "content": question}],
    )
    tool_use = next(block for block in message.content if block.type == "tool_use")
    data = tool_use.input
    return GuardDecision(
        in_scope=data["in_scope"],
        ambiguous=data["ambiguous"],
        reason=data["reason"],
        nearest_metrics=data.get("nearest_metrics", []),
        clarifying_question=data.get("clarifying_question"),
    )
