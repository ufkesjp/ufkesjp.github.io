# Eval Boards — agent

Ontology-grounded analytics agent for Eval Boards, a fictional skateboard
manufacturer. Excluded from Jekyll (`_config.yml`); this is a plain Python
project managed with `uv`, unrelated to how the rest of the site is served.

## Status

Run 1 (foundation) only. No agent loop, tools, or HTML yet — see
`EVAL_BOARDS_KICKOFF.md` at the repo root for the full three-run plan.

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
- `tests/` — pytest suite covering ontology validation and the compiler,
  including regenerating and re-verifying the planted signal.

## Setup

```bash
cd agent
uv sync
uv run python -m data.seed   # regenerate data/eval_boards.duckdb
uv run pytest
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
