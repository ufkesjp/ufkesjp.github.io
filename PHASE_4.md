# Phase 4 — Fix the degraded-path category

Two sessions. Session A is a same-day correction so nothing false is live.
Session B is the real fix. Do them in order; B depends on A being committed.

The same rules from `EVAL_BOARDS_KICKOFF.md` apply — execute only the session
named, stop at its checkpoint, don't commit, and if part of this looks wrong,
stop and say so rather than routing around it.

---

## Background — what's actually broken

The `degraded_path` eval category claims to test whether the agent recovers when
a tool call fails. It doesn't test that.

All five questions (`d01`–`d05` in `agent/evals/questions.yml`) are marked
`triggered_genuine_error: true` in `eval_boards/data/scorecard.json`, but none of
them produced an error:

- `d01`, `d02`, `d03` ask for metrics on quarantined batches (B0050, B0203,
  B0233). These return a successful, held-out result that the agent explains
  correctly. Good behavior — but an empty or excluded result is not a failure.
- `d04` (on_time_ship_rate for ACC0136) and `d05` (veneer_yield for
  LOT-MAP-011) returned ordinary successful answers — 95.3% and 0.363
  respectively. There is nothing degraded about them at all.

So the published `recovery_rate: 1.0` is measuring nothing, and the page text
asserting these runs "hit a real error (not just an empty result)" is false.

---

## Session A — Stop publishing the false claim (30 min)

> Read CLAUDE.md and PHASE_4.md. Execute Session A only, then stop.
>
> The `degraded_path` eval category does not test what it claims to test — see
> the Background section of PHASE_4.md. This session is a truthfulness
> correction only. Do not rewrite the questions, do not re-run the agent, and
> do not make any API calls.
>
> 1. Rename the category from `degraded_path` to `held_out_results` everywhere
>    it appears: `agent/evals/questions.yml`, `agent/evals/test_evals.py`,
>    `eval_boards/data/scorecard.json`, and any label in the inline JS in
>    `eval_boards/index.html`.
>
> 2. Rename the `recovery_rate` field to `handled_correctly_rate`. It is not
>    measuring recovery.
>
> 3. Replace the `triggered_genuine_error` assertion with
>    `handled_exclusion_correctly`, and re-score honestly from the existing
>    trace data: `d01`–`d03` test held-out batch behavior and pass;
>    `d04` and `d05` are ordinary successful queries with no exclusion involved,
>    so they do not belong in this category at all. Move them to `answerable`
>    and rescore. Report the corrected per-category totals to me before writing
>    anything to scorecard.json.
>
> 4. In `eval_boards/index.html`, rewrite the scorecard section intro. Remove
>    the sentence claiming five runs hit a real error. Describe the category as
>    what it is: questions whose underlying data is held out by an approved
>    quarantine, where the agent must explain the exclusion rather than report a
>    misleading zero.
>
> 5. Add static fallback text to `eval_boards/index.html` for the headline
>    scorecard numbers and the flagship trace's headline finding, so the page
>    says something substantive without JavaScript. JS should replace this
>    content on load, not sit alongside it.
>
> **Checkpoint:** no claim about error recovery appears anywhere in the repo or
> on the page; category totals match the underlying trace evidence; page renders
> meaningfully with JS disabled. Stop. Do not begin Session B.

---

## Session B — Build a real degraded-path test (about an hour, plus API spend)

> Read CLAUDE.md and PHASE_4.md. Execute Session B only, then stop.
> Session A must be committed before starting this.
>
> Build a genuine degraded-path category that tests whether the agent recovers
> when a tool call actually fails.
>
> 1. Write five new questions as category `degraded_path` in
>    `agent/evals/questions.yml`. Each must cause the agent's natural first tool
>    call to return an error, not an empty result set. Use a range of failure
>    modes:
>
>    - a filter value that does not exist in the ontology's allowed set
>    - a grain the metric does not support
>    - a link traversal from an object that has no links of that type
>    - a metric requested at an object type it isn't defined for
>    - a malformed or out-of-range argument (e.g. an impossible date window)
>
>    The distinction that matters: a query that succeeds and returns zero rows
>    is a valid empty result and does NOT belong here. Only calls that raise or
>    return an error payload count. If you are unsure which side a question
>    falls on, stop and ask me before writing it.
>
> 2. For each, the pass condition is that the agent (a) receives a genuine
>    error, (b) does not fabricate a number, (c) revises its approach — a
>    different tool, a corrected argument, or an honest explanation of what it
>    can't do — and (d) does not hit the iteration limit. Assert against the
>    trace, not the prose.
>
> 3. Add a `first_call_errored` assertion that reads the trace and fails the
>    question if no tool call actually returned an error. This is the guard
>    against the same problem recurring: a question that doesn't error should
>    fail the eval outright rather than silently passing.
>
> 4. Run the smoke subset first and report results before the full sweep.
>    Then run the full set and regenerate `eval_boards/data/scorecard.json`.
>
> 5. Re-record `eval_boards/data/traces/recovery.json` using whichever of the
>    five new questions produces the clearest recovery narrative — a real error,
>    a visible correction, an honest final answer. Verify the old recovery trace
>    is replaced, not appended.
>
> 6. Update `eval_boards/index.html`: restore the degraded-path description in
>    the scorecard section, now accurate, and refresh the static fallback
>    numbers to match the new scorecard.
>
> **Checkpoint:** every degraded-path question demonstrably errored on a real
> tool call; recovery rate reflects actual recoveries; the recovery trace shows
> a genuine failure and correction. Report the new totals and tell me which
> questions, if any, the agent failed. Stop.

---

## What to watch when reviewing

- **Don't let the recovery rate come back as 5/5.** If every question passes
  first try, the failures were probably too easy to route around. A real
  recovery test should be hard enough that one or two fail.
- **Read the new recovery trace yourself** before it goes on the page. The
  question is whether a stranger can see the error, see the correction, and
  believe the agent noticed rather than got lucky.
- **Publish the failures.** The static scorecard text should name what didn't
  pass. A page that reports 30/30 is less credible than one reporting 27/30
  with an explanation.
