# Eval Boards — agent

Ontology-grounded analytics agent for Eval Boards, a fictional skateboard
manufacturer. Excluded from Jekyll (`_config.yml`); this is a plain Python
project managed with `uv`, unrelated to how the rest of the site is served.

## Status

Run 1 (foundation), Run 2 (agent), and Run 3 (eval harness + public page)
done — see `EVAL_BOARDS_KICKOFF.md` at the repo root for the full
three-run plan. No GitHub Action for the evals (skipped for v1, per the
plan); run `uv run pytest evals` locally and commit the regenerated
scorecard.

## Layout

- `ontology/eval_boards.yml` — object types, links, actions, metrics. The
  single source of truth for what the agent can talk about.
- `ontology/schema.py` — Pydantic models that parse and validate the YAML,
  failing loudly on any referential-integrity problem (a link to an
  undefined object type, a metric filtering on a property that doesn't
  exist, an action precondition naming an unknown field).
- `ontology/compiler.py` — turns a metric name + filters + grain, or a link
  name + id, into parameterized SQL. Nothing here executes free-form SQL;
  every metric, filter, grain dimension, and link is validated against the
  loaded ontology before any SQL is built.
- `data/seed.py` — deterministic synthetic data generator (fixed seed) that
  writes `data/eval_boards.duckdb`. Plants one discoverable signal: a maple
  veneer lot consumed by 12 batches across two press lines, whose decks
  show an elevated delamination claim rate once compared at matched (90
  day) field maturity.
- `ontology/tools.py` — generates the six Anthropic tool schemas
  (`list_available_metrics`, `get_metric`, `compare_periods`, `get_object`,
  `traverse_link`, `propose_action`) from the loaded ontology at import
  time, and dispatches tool calls to the compiler.
- `ontology/describe.py` — reads the ontology and `data/eval_boards.duckdb`
  and writes `eval_boards/data/datamodel.json` (links, object types with live
  row counts and columns, and sample rows connecting to the flagship trace's
  lot/batch/claim). Regenerate it with:

  ```bash
  uv run python -m ontology.describe
  ```

  after any change to `eval_boards.yml` or the seed data. The ontology
  diagram in `eval_boards/index.html` is hand-authored inline SVG, not
  generated from this file — `tests/test_datamodel.py` guards against it
  drifting out of sync by asserting every object type and link name appears
  in both the SVG markup and `datamodel.json`.
- `runtime/guard.py` — a coverage check, separate from the agent's own
  judgment, that decides whether a question is answerable at all before the
  loop starts.
- `runtime/loop.py` — the plain Anthropic tool-use loop (no framework),
  12 iterations max.
- `runtime/trace.py` — structured JSON logging of every run: guard
  decision, each tool call and result, token counts, latency, final answer.
- `runtime/approve.py` — the human half of the closed loop:
  `uv run python -m runtime.approve <action_id>` flips a pending action to
  approved. An approved `quarantine_batch` then changes what
  `build_metric_query` returns — the whole point of the actions table.
- `runtime/cli.py` — `uv run python -m runtime.cli "question"` runs the
  agent once and writes a trace to `eval_boards/data/traces/`.
- `tests/` — pytest suite covering ontology validation, the compiler, the
  tools, and the guard/loop (against a fake Anthropic client — the test
  suite makes no real API calls).
- `evals/questions.yml` — 30 golden questions (17 answerable, 6 out of
  scope, 4 ambiguous, 3 held-out-results), with a 5-question `smoke` subset.
- `evals/test_evals.py`, `evals/conftest.py` — the eval harness. Unlike
  `tests/`, this makes real Anthropic API calls and writes
  `eval_boards/data/scorecard.json`:

  ```bash
  uv run pytest evals --subset smoke   # 5 questions, run this first
  uv run pytest evals --subset full    # all 30, only once smoke is green
  ```

## The public page

`eval_boards/index.html` (site root, not under `agent/`) is a static page
using the site's existing neubrutalist design system — the flagship trace,
the scorecard, and the other five traces are fetched client-side from
`eval_boards/data/*.json` and rendered with vanilla JS, no framework or
CDN. That `fetch()` fails over `file://`, so local testing needs a server:

```bash
python3 -m http.server 8000   # from the repo root
# then open http://localhost:8000/eval_boards/
```

## Setup

```bash
cd agent
uv sync
uv run python -m data.seed   # regenerate data/eval_boards.duckdb
uv run pytest
```

## Running the agent

Needs `ANTHROPIC_API_KEY` in the repo-root `.env` (loaded automatically —
see `runtime/env.py`). If the key is a Console identity-linked key rather
than a plain project key, also set `ANTHROPIC_WORKSPACE_ID` in `.env`.

```bash
uv run python -m runtime.cli "Delamination claims are up - what's going on?"
uv run python -m runtime.approve ACT-xxxxxxxxxx
```

## Querying a metric

```python
import duckdb
from ontology.schema import load_ontology
from ontology.compiler import build_metric_query

ontology = load_ontology()
con = duckdb.connect("data/eval_boards.duckdb")

query = build_metric_query(ontology, "delamination_claim_rate", grain=["batch"])
con.execute(query.sql, query.params).fetchall()
```
