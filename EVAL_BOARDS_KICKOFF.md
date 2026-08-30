# Eval Boards — Weekend Build Plan

An ontology-grounded analytics agent, built inside `ufkesjp.github.io`.
Three Claude Code runs. Paste each prompt at the start of a session.

---

## Before you start

1. Repo cloned locally and open in VS Code.
2. On a working branch: `git checkout -b eval-boards`.
3. `.gitignore` at the repo root containing `.DS_Store`, `.env`, `__pycache__/`,
   and `.venv/`.
4. `.env` at the repo root containing `ANTHROPIC_API_KEY=...` from the Claude
   Console. Not your Claude.ai login — a separate, funded API account with a
   monthly spend cap set.
5. `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
6. This file saved at the repo root as `EVAL_BOARDS_KICKOFF.md`.

### macOS notes

- Let uv manage the interpreter: `uv python install 3.11`. Don't use system
  Python or Homebrew Python.
- Use `python3`, not `python` — there is no bare `python` on macOS.
- Add `.DS_Store`, `.env`, and `__pycache__/` to `.gitignore` before Run 1.
- APFS is case-insensitive but GitHub is not. Use `git mv` for any rename, or a
  case-only change will look fine locally and 404 in production.

Budget $10–20 in API spend across the weekend. Debug the agent loop on Haiku 4.5
($1/$5 per million tokens), record final traces and the scorecard on Sonnet 5
($2/$10). Cache the system prompt and tool schemas — cache hits bill at 10% of
fresh input. Your key stays local: nothing in this build puts it on the site.

---

## Step 0 — Preflight (paste this before Run 1)

Run this as its own message in Claude Code. It changes nothing; it only confirms
the environment is ready. Fix anything it flags before starting Run 1.

> Preflight check only — do not create, modify, or delete any files, and do not
> begin Run 1. Verify each item below and report pass/fail for each with the
> evidence you used:
>
> 1. Current working directory is the root of the `ufkesjp.github.io` repo, and
>    `CLAUDE.md`, `README.md`, `_config.yml`, and `index.html` are all present.
> 2. `EVAL_BOARDS_KICKOFF.md` exists at that root.
> 3. `git rev-parse --abbrev-ref HEAD` returns `eval-boards`, not `main`.
> 4. `git status` is clean apart from `.gitignore` and this plan file — no
>    uncommitted work in progress that a build would disturb.
> 5. `.gitignore` exists at the root and contains `.DS_Store`, `.env`,
>    `__pycache__/`, and `.venv/`.
> 6. `.env` exists at the root and contains a non-empty `ANTHROPIC_API_KEY`.
>    Confirm only that the variable is set and non-empty — do not print, echo,
>    or repeat the key value anywhere in your response.
> 7. `git check-ignore -v .env` confirms `.env` is ignored. This one is
>    non-negotiable: if it fails, stop and tell me, and do not proceed.
> 8. `uv --version` succeeds, and `uv python list` shows a 3.11 or newer
>    interpreter available.
> 9. `agent/` and `eval_boards/` do not already exist. If either does, stop and
>    tell me rather than merging into or overwriting it.
>
> If every item passes, say so and wait. Do not start Run 1 until I tell you to.

---

## Rules for every run — do not deviate

These apply to all three runs. If a prompt below conflicts with these, these win.

1. **Execute only the run named.** Stop at that run's checkpoint. Do not begin
   the next run, do not scaffold for it, do not create placeholder files for it.
2. **Stay inside the target layout.** Do not create files or directories outside
   the paths listed below without asking first.
3. **No dependencies beyond the listed ones.** duckdb, pydantic, pyyaml,
   anthropic, pytest. Anything else requires asking, with a reason.
4. **No build step, bundler, npm, framework, or CSS library** anywhere in this
   repo — see CLAUDE.md. The site is hand-written HTML and stays that way.
5. **Do not modify existing portfolio files** except where a run explicitly says
   to (`_config.yml` in Run 1; `projects/index.html` and `index.html` in Run 3).
   Never touch `css/style.css` — use existing variables and classes.
6. **Do not commit.** Leave staging and committing to me.
7. **Do not delete anything** without asking.
8. **If part of the plan looks wrong, stop and say so.** Do not silently route
   around it, substitute a different approach, or "improve" the spec. I would
   rather answer a question than discover a redesign.
9. **Do not fabricate outputs.** Traces and scorecards must come from real
   model calls and real queries. If something can't run, say so; never write a
   plausible-looking artifact by hand.
10. **End each run with a summary**: files created, files modified, anything you
    skipped or flagged, and whether the checkpoint criteria are met.

---

## Target layout

```
agent/                          # Python project — excluded from Jekyll
  ontology/
    eval_boards.yml                 # object types, links, actions, metrics
    schema.py                   # Pydantic models that validate eval_boards.yml
    compiler.py                 # ontology -> SQL
    tools.py                    # ontology -> Anthropic tool schemas
  runtime/
    loop.py                     # agent tool-use loop
    guard.py                    # coverage check / refusal
    trace.py                    # structured run logging
  data/
    seed.py                     # synthetic data generator
    eval_boards.duckdb              # committed, reproducible
  evals/
    questions.yml               # 25 golden questions
    test_evals.py
  pyproject.toml
  README.md

eval_boards/                # the public artifact
  index.html                    # case study + trace explorer
  data/
    traces/*.json
    scorecard.json
```

---

## Run 1 — Foundation (target: 2 hours)

> I'm adding a new subproject to this portfolio repo: an ontology-grounded
> analytics agent for a fictional skateboard manufacturer called Eval Boards.
> Read CLAUDE.md first. This run is foundation only — no agent code yet.
>
> Create a Python project at `agent/` using uv, Python 3.11+, dependencies:
> duckdb, pydantic, pyyaml, anthropic, pytest. Add `agent/` and
> `eval_boards/data/` to a new `exclude:` list in `_config.yml` so Jekyll
> ignores them.
>
> **1. Ontology spec** at `agent/ontology/eval_boards.yml` with four sections:
>
> - `object_types`: Deck, ProductionBatch, MaterialLot, Supplier,
>   QualityInspection, WarrantyClaim, Order, RetailAccount, PressLine. Each has
>   typed properties and a primary key.
> - `links`: named, directional, with cardinality. At minimum —
>   ProductionBatch consumes MaterialLot (many-to-many), MaterialLot supplied_by
>   Supplier, Deck produced_by ProductionBatch, ProductionBatch ran_on PressLine,
>   WarrantyClaim concerns Deck, Order placed_by RetailAccount, Order
>   fulfilled_from ProductionBatch.
> - `actions`: quarantine_batch, open_supplier_corrective_action, reroute_order.
>   Each with typed parameters, preconditions expressed as boolean rules, and a
>   required-evidence field.
> - `metrics`: first_pass_yield, scrap_cost_per_batch, veneer_yield,
>   on_time_ship_rate, delamination_claim_rate. Each carries: definition (prose),
>   grain, allowed_filters, owner, and a `rationale` field.
>
> For `delamination_claim_rate`, define it as claims per 100 decks at 90-day
> field maturity, and write a rationale explaining that raw claims over units
> shipped biases toward recent batches because defects surface with use. This
> rationale is a deliverable, not a comment — make it good.
>
> **2. Validation** at `agent/ontology/schema.py` — Pydantic models that parse
> and validate the YAML. Fail loudly on: links referencing undefined object
> types, metrics referencing undefined properties, actions with preconditions
> naming unknown fields.
>
> **3. Seed data** at `agent/data/seed.py` — deterministic, seeded RNG, writes
> `agent/data/eval_boards.duckdb`. 18 months of history, ~400 production batches,
> ~60 material lots, 8 suppliers, 3 press lines, ~12,000 decks, ~9,000 orders,
> ~600 warranty claims.
>
> Plant exactly one discoverable signal: a single maple veneer lot from one
> supplier, consumed by roughly a dozen batches, whose decks show a
> delamination claim rate about 3x baseline at matched maturity. Make it real
> but not trivially obvious — the affected batches should span two press lines
> so line is a red herring.
>
> **4. SQL compiler** at `agent/ontology/compiler.py` — functions that turn a
> metric name plus filters and grain into parameterized SQL, and that resolve
> link traversals into joins. Nothing in this project ever executes free-form
> SQL. Raise on any metric, filter, or link not present in the ontology.
>
> Write pytest tests for the compiler and validation. Do not write the agent
> loop, tools, or any HTML this run.
>
> Stop at the Run 1 checkpoint and summarize. Do not begin Run 2.

**Checkpoint:** `uv run pytest` passes, and you can query a metric from a Python
REPL. Commit.

---

## Run 2 — Agent (target: 4 hours)

> Continue the Eval Boards subproject. Read `agent/ontology/eval_boards.yml` and
> `agent/ontology/compiler.py` first.
>
> **1. Tool schemas** at `agent/ontology/tools.py` — generate Anthropic tool
> definitions *from* the ontology at import time. Never hand-write them. Six
> tools: `list_available_metrics`, `get_metric`, `compare_periods`,
> `get_object`, `traverse_link`, `propose_action`. Enum values for metric names,
> link names, and filterable fields come from the YAML, so adding a metric
> changes the agent's capabilities with no code change.
>
> `propose_action` evaluates preconditions and writes to a real `actions` table
> in DuckDB with status `pending_approval`, capturing the action type, target
> object, parameters, supporting evidence, and timestamp. It never mutates
> warehouse fact data. If a precondition fails, it returns the failure reason
> rather than raising.
>
> **1b. Closed loop — this is the part that makes it an agent.** Write an
> approval CLI (`uv run python -m agent.runtime.approve <action_id>`) that flips
> status to `approved`. The compiler must then honor approved actions: batches
> with an approved `quarantine_batch` are excluded from downstream metric
> queries, with the exclusion surfaced in the tool result so the agent can say
> which batches were held out and why. An approved action changes what the agent
> subsequently sees. Without this the project is only formatting proposals.
>
> **2. Coverage guard** at `agent/runtime/guard.py` — given a question, decide
> whether the ontology can answer it, before the agent loop starts. Return a
> structured refusal naming what's missing and listing the nearest available
> metrics. This is deliberately separate from the model's own judgment; it's a
> hard boundary, not a suggestion.
>
> **3. Agent loop** at `agent/runtime/loop.py` — a plain Anthropic tool-use
> loop, model `claude-sonnet-5`, max 12 iterations. Use `claude-haiku-4-5-20251001` while
> debugging and switch to Sonnet only for the final recorded traces. No agent framework. Keep
> it readable; I need to explain every line in an interview. The system prompt
> must instruct the model to cite the metric definition it used and to state
> when a finding is correlational rather than causal.
>
> **4. Trace logging** at `agent/runtime/trace.py` — every run writes JSON:
> question, guard decision, each tool call with arguments and results, token
> counts, latency, final answer, any actions proposed, and — where a tool call
> fails or returns empty — the retry and what the agent did next.
>
> **5. Record traces.** Write a CLI (`uv run python -m agent.runtime.cli
> "question"`) and use it to record six traces into
> `eval_boards/data/traces/`. The flagship one:
>
>   "Delamination claims are up on the Pro series — what's going on?"
>
> The agent should pull claim rate by batch at matched maturity, traverse to
> consumed material lots, identify the suspect lot, find other batches that
> consumed it, and propose quarantining them. Also include:
>
> - a trace where the coverage guard refuses out of scope
> - a trace where a precondition blocks an action
> - **a recovery trace** — ask something whose obvious first tool call returns
>   empty or errors (a filter value that doesn't exist, a lot with no claims
>   yet), and confirm the agent revises its approach rather than fabricating or
>   giving up. Recovery under failure is much of what distinguishes an agent
>   engineer from someone who has read the tool-use docs, so do not let this one
>   slide if it takes a few attempts to get right.
> - a post-approval trace — approve the quarantine from the flagship run, then
>   re-ask the delamination question and show the agent accounting for the held
>   batches
>
> Iterate on the system prompt until the flagship trace is clean. That trace is
> the centerpiece of the whole project.
>
> Stop at the Run 2 checkpoint and summarize. Do not begin Run 3, and do not
> write any HTML this run.

**Checkpoint:** six traces on disk, flagship one reaches the right lot, approving
a quarantine visibly changes the next answer. Commit.

---

## Run 3 — Proof and presentation (target: 3 hours)

> Continue Eval Boards. This run produces the eval harness and the public
> page. Read CLAUDE.md again before writing any HTML — the neubrutalist design
> system is non-negotiable and there is no build step.
>
> **1. Golden questions** at `agent/evals/questions.yml` — 30 total:
> 15 answerable (each with expected metric calls, expected links traversed, and
> key facts the answer must contain), 6 out-of-scope that must be refused by the
> guard, 4 ambiguous ones the agent must ask about rather than assume, and 5
> **degraded-path** questions where a tool returns empty or errors — scored on
> whether the agent recovers or fabricates.
>
> Tag 5 of these as a `smoke` subset and add a `--subset smoke` flag to the
> runner. Iterate on smoke; run the full 30 only when smoke is green. That flag
> is most of your API budget.
>
> **2. Eval harness** at `agent/evals/test_evals.py` — pytest, assertions
> against the trace, not the prose. Score: answer accuracy, tool-call precision
> (did it call the right tools with right arguments), refusal rate on
> out-of-scope, **recovery rate on the degraded path**, and mean iterations.
> Write `eval_boards/data/scorecard.json` with per-category results and a
> timestamp.
>
> **3. GitHub Action (optional — skip for v1)** at `.github/workflows/evals.yml` — runs on push to paths
> under `agent/`, executes evals, commits an updated scorecard. Needs
> `ANTHROPIC_API_KEY` as a repo secret. If you'd rather keep the key off GitHub
> entirely, skip this and run `uv run pytest agent/evals` locally, committing the
> regenerated scorecard yourself. Note both paths in the README.
>
> **4. Public page** at `eval_boards/index.html`, using the existing design
> system and `css/style.css`. Sections in this order:
>
> - Headline: what this is, in one sentence, plus a plain statement that the
>   data is synthetic and models a fictional manufacturer.
> - The flagship trace, rendered as expandable steps — question, guard decision,
>   each tool call and result, the proposed action, the final answer. This goes
>   above the fold. It is the thing recruiters will actually look at.
> - Scorecard, read from `scorecard.json` at page load, including the refusal
>   rate with a sentence explaining why measuring refusals matters.
> - The other four traces, collapsed.
> - The `delamination_claim_rate` rationale, quoted in full, framed as the kind
>   of definitional choice that has to be settled before an agent can be trusted.
> - Architecture: the object/link/action model and why tool schemas are
>   generated from the ontology rather than hand-written.
>
> Vanilla JS only, no framework, no CDN. Add a card for this project to
> `projects/index.html` and the landing page, matching existing card markup.
>
> Note in the README that local testing needs `python3 -m http.server` because
> `fetch()` fails over `file://`.
>
> Stop at the Run 3 checkpoint and summarize. Do not start anything from the
> "After the weekend" section.

**Checkpoint:** page renders locally, scorecard loads, flagship trace reads
well to someone who knows nothing about the project.

---

## After the weekend

In rough priority order, each a standalone session:

1. **Add dbt** (`dbt-duckdb`) as a refactor of the seed script's transforms —
   gives you lineage docs and a named stack item.
2. **Supabase action layer** — real approvals table with row-level security,
   plus an Edge Function for a live demo. Add a scheduled ping so the free
   project doesn't pause after 7 days.
3. **Expand to 50 golden questions** and add LLM-as-judge for prose quality.
4. **Write the interview narrative** — one page on why definitions precede
   agents, drawing the line from your Foundry ontology work to this.

---

## The two sentences that have to land

On the page, and in interviews:

> The hard part of an analytics agent isn't getting an answer. It's making sure
> the answer means what a VP will assume it means when they repeat it.

> I measured how often it correctly refuses, because confident wrong answers
> are the failure mode that actually costs companies money.
