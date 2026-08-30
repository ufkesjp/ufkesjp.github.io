"""Generates eval_boards/data/datamodel.json from the ontology + warehouse.

    uv run python -m ontology.describe

Reads the loaded Ontology (agent/ontology/eval_boards.yml) and the seeded
warehouse (agent/data/eval_boards.duckdb) and writes every link, every object
type with a live row count and column list, and a handful of connected
sample rows to eval_boards/data/datamodel.json. Nothing in the output is
hand-typed — regenerate this file whenever the ontology or the seed data
changes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from data.seed import DB_PATH

from .compiler import LINK_TABLES
from .schema import Ontology, load_ontology

OUT_PATH = Path(__file__).resolve().parents[2] / "eval_boards" / "data" / "datamodel.json"

# The lot, batch, and claim at the center of the flagship trace (see
# agent/data/seed.py's planted signal) — samples are chosen so a reader can
# find the same ids here that appear in that trace.
FLAGSHIP_LOT_ID = "LOT-MAP-011"
FLAGSHIP_BATCH_ID = "B0050"
FLAGSHIP_CLAIM_ID = "WC00438"

SAMPLE_SIZE = 5


def _links(ontology: Ontology) -> list[dict]:
    return [
        {
            "source": link.from_,
            "name": link.name,
            "target": link.to,
            "cardinality": link.cardinality,
            "description": link.description,
        }
        for link in ontology.links
    ]


def _columns(con: duckdb.DuckDBPyConnection, table: str) -> list[dict]:
    rows = con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = ? ORDER BY ordinal_position",
        [table],
    ).fetchall()
    return [{"name": name, "type": data_type} for name, data_type in rows]


def _object_types(ontology: Ontology, con: duckdb.DuckDBPyConnection) -> list[dict]:
    result = []
    for name, obj_type in ontology.object_types.items():
        table = LINK_TABLES[name]
        row_count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        result.append({
            "name": name,
            "description": obj_type.description,
            "row_count": row_count,
            "columns": _columns(con, table),
        })
    return result


def _rows_as_dicts(con: duckdb.DuckDBPyConnection, sql: str, params: list) -> list[dict]:
    cursor = con.execute(sql, params)
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _connected_sample(
    con: duckdb.DuckDBPyConnection, table: str, primary_key: str, required_id: str
) -> list[dict]:
    """Fetch SAMPLE_SIZE rows from `table`, guaranteeing `required_id` is one
    of them — the rest are the lowest-id rows, so the sample is deterministic
    across regenerations."""
    required = _rows_as_dicts(
        con, f"SELECT * FROM {table} WHERE {primary_key} = ?", [required_id]
    )
    others = _rows_as_dicts(
        con,
        f"SELECT * FROM {table} WHERE {primary_key} != ? "
        f"ORDER BY {primary_key} LIMIT {SAMPLE_SIZE - len(required)}",
        [required_id],
    )
    return sorted(required + others, key=lambda row: row[primary_key])


def _samples(con: duckdb.DuckDBPyConnection) -> dict:
    return {
        "MaterialLot": _connected_sample(con, "material_lots", "lot_id", FLAGSHIP_LOT_ID),
        "ProductionBatch": _connected_sample(
            con, "production_batches", "batch_id", FLAGSHIP_BATCH_ID
        ),
        "WarrantyClaim": _connected_sample(
            con, "warranty_claims", "claim_id", FLAGSHIP_CLAIM_ID
        ),
    }


def build_datamodel(ontology: Ontology, con: duckdb.DuckDBPyConnection) -> dict:
    return {
        "links": _links(ontology),
        "object_types": _object_types(ontology, con),
        "samples": _samples(con),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    ontology = load_ontology()
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        datamodel = build_datamodel(ontology, con)
    finally:
        con.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(datamodel, indent=2, default=str))
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
