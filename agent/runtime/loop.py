"""The agent tool-use loop.

Plain Anthropic tool-use loop, no framework: call the model, run whatever
tools it asked for, feed the results back, repeat until it stops asking for
tools or we hit MAX_ITERATIONS. The only structure beyond that is the
coverage guard gating the loop before it starts (see runtime/guard.py) and
the trace recorder wrapping every step (see runtime/trace.py).
"""

from __future__ import annotations

import json
import time

import anthropic

from ontology.schema import Ontology, load_ontology
from ontology.tools import TOOL_SCHEMAS, execute_tool
from runtime.env import make_client
from runtime.guard import check_coverage
from runtime.trace import Trace, ToolCallRecord

DEFAULT_MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """\
You are an analytics agent for Eval Boards, a skateboard manufacturer. You \
answer questions using only the tools provided — list_available_metrics, \
get_metric, compare_periods, get_object, traverse_link, and propose_action. \
Never invent a metric, link, field, or number that isn't backed by a tool \
result.

Rules:
- Investigate open-ended questions ("X is up, what's going on?") all the \
way through in one pass: measure the pattern, traverse links to find what \
the affected records have in common (a shared lot, supplier, or press \
line), and — if a specific cause and specific affected records emerge — \
propose the appropriate action yourself rather than stopping to ask which \
of several obvious next steps to take.
- You have a hard budget of {max_iterations} turns, not tool calls — a \
single turn can request many tool calls at once and they run in parallel. \
Be efficient: look for the handful of batches most worth investigating \
(the ones clearly separated from the pack, not every batch with any \
nonzero reading) and traverse from those in one or two batched turns \
rather than widening the net turn after turn. Aim to have your answer by \
roughly turn 6-8, leaving headroom rather than using all {max_iterations}.
- get_metric accepts more than one grain dimension at once (e.g. \
["batch", "press_line"]) — read what you already have before reaching for \
another tool call to get information you may already have. But splitting \
by more dimensions (e.g. ["batch", "month"] instead of just ["batch"]) \
divides each batch's already-small sample into even smaller ones, so \
individual cells get noisier and less comparable. To rank or compare \
batches against each other, use the coarsest grain that still answers the \
question (usually just ["batch"]) — don't call a single fine-grained cell \
(one batch in one month) "the highest rate of any batch" when that's \
comparing a small sub-sample against other batches' full totals.
- To find what several affected records share, anchor on your *single* \
most extreme record first: traverse its links and treat what it's \
connected to as your short candidate list (a batch typically consumes \
only 4-5 lots total). Then check which of those *specific* candidates also \
turn up for your other affected records. This is much more reliable than \
scanning many records for any id that happens to repeat — a lot used by a \
large share of all batches fleet-wide (a generic, commonly-used lot) will \
turn up in a couple of your affected records purely by chance and that is \
weak evidence, whereas a lot tied to your most extreme reading recurring \
even once more among a handful of other affected records is a real \
finding. Don't discount your single most-elevated affected record as \
"probably noise" — anchor there, don't dismiss it.
- You don't need a second, different metric to corroborate a recurring \
link you found — that recurrence is itself the evidence. Most metrics in \
this ontology measure something unrelated to any one specific defect, so a \
metric that doesn't move for your candidate doesn't defeat the finding, \
and one that does move for an unrelated candidate doesn't make it real — \
lots of numbers will vary from lot to lot for reasons that have nothing to \
do with the question you're investigating.
- When you report a number, name the metric and cite its definition (from \
get_metric's `definition` field). State explicitly when a finding is \
correlational — an elevated rate, a shared lot — rather than causal; you \
have observational data, not a controlled experiment.
- If a tool call returns an error, an empty result, or a "found": false, do \
not fabricate a plausible-looking answer and do not give up immediately. \
Revise your approach — a different filter value, a different link, check \
whether an id you assumed actually exists — then say plainly what you \
could not determine if it still doesn't resolve.
- propose_action only writes a pending_approval row; say so, and that a \
human must approve it separately before it changes what any tool sees. \
Match the action to what the evidence implicates — quarantine_batch each \
specific batch you can name as affected, rather than a broader \
supplier-level action the evidence doesn't specifically support.
- If get_metric reports excluded_batches, mention which batches were held \
out and why (an approved quarantine) when it's relevant to the question.
- Keep your final answer proportionate: a few short paragraphs naming the \
specific implicated batches/lot/supplier. The trace log already has every \
tool call — don't re-list them in the answer.
"""

MAX_ITERATIONS = 12
SYSTEM_PROMPT = SYSTEM_PROMPT.format(max_iterations=MAX_ITERATIONS)


def _looks_empty(result: dict) -> bool:
    if "error" in result:
        return False  # tracked separately via is_error
    if "rows" in result and isinstance(result["rows"], list) and not result["rows"]:
        return True
    if result.get("found") is False:
        return True
    return False


def run_agent(
    question: str,
    *,
    ontology: Ontology | None = None,
    con,
    model: str = DEFAULT_MODEL,
    client: anthropic.Anthropic | None = None,
) -> Trace:
    ontology = ontology or load_ontology()
    client = client or make_client()
    trace = Trace(question=question, model=model)
    start = time.monotonic()

    try:
        guard_decision = check_coverage(question, ontology, client=client)
        trace.guard_decision = guard_decision.to_dict()

        if not guard_decision.in_scope:
            nearest = ", ".join(guard_decision.nearest_metrics) or "none"
            trace.refused = True
            trace.final_answer = (
                f"This is out of scope for what I can answer: {guard_decision.reason} "
                f"Nearest available metrics: {nearest}."
            )
            return trace

        if guard_decision.ambiguous:
            trace.asked_clarification = True
            trace.final_answer = (
                guard_decision.clarifying_question
                or "Could you clarify what you're asking?"
            )
            return trace

        messages: list[dict] = [{"role": "user", "content": question}]

        for iteration in range(1, MAX_ITERATIONS + 1):
            response = client.messages.create(
                model=model,
                max_tokens=6144,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
            trace.token_usage.append(
                {
                    "iteration": iteration,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }
            )
            messages.append({"role": "assistant", "content": response.content})

            tool_uses = [block for block in response.content if block.type == "tool_use"]
            if not tool_uses:
                text_blocks = [block.text for block in response.content if block.type == "text"]
                answer = "\n".join(text_blocks).strip()
                if not answer and response.stop_reason == "max_tokens":
                    answer = (
                        "The model's response was cut off by the token limit "
                        "before it produced any final text."
                    )
                trace.final_answer = answer
                trace.iterations = iteration
                return trace

            tool_results = []
            for tool_use in tool_uses:
                try:
                    result = execute_tool(
                        tool_use.name, tool_use.input, ontology=ontology, con=con
                    )
                    is_error = False
                except Exception as exc:  # noqa: BLE001 - surfaced to the model, not swallowed
                    result = {"error": str(exc)}
                    is_error = True

                is_empty = (not is_error) and _looks_empty(result)
                trace.tool_calls.append(
                    ToolCallRecord(
                        name=tool_use.name,
                        arguments=tool_use.input,
                        result=result,
                        is_error=is_error,
                        is_empty=is_empty,
                    )
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result, default=str),
                        **({"is_error": True} if is_error else {}),
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        trace.iterations = MAX_ITERATIONS
        trace.final_answer = (
            f"Reached the {MAX_ITERATIONS}-iteration limit without a final answer."
        )
        return trace
    finally:
        trace.latency_seconds = round(time.monotonic() - start, 3)
