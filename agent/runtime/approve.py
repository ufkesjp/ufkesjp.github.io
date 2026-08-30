"""Approval CLI — the human half of the closed loop.

    uv run python -m runtime.approve <action_id>

Flips one pending_approval action to approved. This is the only way an
action ever takes effect: an approved quarantine_batch changes what
build_metric_query returns (see ontology/compiler.py), without ever writing
to production_batches or any other warehouse fact table.
"""

from __future__ import annotations

import sys
from datetime import datetime

import duckdb

from data.seed import DB_PATH
from ontology.compiler import ensure_actions_table


def approve(action_id: str) -> str:
    con = duckdb.connect(str(DB_PATH))
    try:
        ensure_actions_table(con)
        row = con.execute(
            "SELECT status FROM actions WHERE action_id = ?", [action_id]
        ).fetchone()
        if row is None:
            raise ValueError(f"no action found with id {action_id!r}")
        status = row[0]
        if status != "pending_approval":
            raise ValueError(
                f"action {action_id} is '{status}', not pending_approval; not changing it"
            )
        con.execute(
            "UPDATE actions SET status = 'approved', approved_at = ? WHERE action_id = ?",
            [datetime.utcnow(), action_id],
        )
        return action_id
    finally:
        con.close()


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: uv run python -m runtime.approve <action_id>", file=sys.stderr)
        raise SystemExit(1)
    try:
        approved_id = approve(sys.argv[1])
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"approved {approved_id}")


if __name__ == "__main__":
    main()
