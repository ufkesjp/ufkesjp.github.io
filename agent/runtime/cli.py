"""Run the agent on one question and record a trace.

    uv run python -m runtime.cli "question" [--model MODEL] [--out NAME.json]

Connects read-write to the real eval_boards.duckdb (propose_action needs to
write to it), runs the loop, and writes a trace JSON to
eval_boards/data/traces/.
"""

from __future__ import annotations

import argparse
import re

import duckdb

from data.seed import DB_PATH
from ontology.schema import load_ontology
from runtime.env import load_dotenv_if_present
from runtime.loop import DEFAULT_MODEL, run_agent
from runtime.trace import TRACE_DIR, write_trace


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:60] or "trace"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", default=None, help="trace filename (default: slug of question)")
    args = parser.parse_args()

    load_dotenv_if_present()

    ontology = load_ontology()
    con = duckdb.connect(str(DB_PATH))
    try:
        trace = run_agent(args.question, ontology=ontology, con=con, model=args.model)
    finally:
        con.close()

    out_path = TRACE_DIR / (args.out or f"{_slug(args.question)}.json")
    write_trace(trace, out_path)

    print(trace.final_answer)
    print(f"\n[{trace.iterations} iterations, {trace.latency_seconds}s, trace: {out_path}]")


if __name__ == "__main__":
    main()
