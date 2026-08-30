"""Sanity checks on the seeded warehouse: rough row counts, and that the
planted delamination signal is actually present in the data at the
maturity-adjusted grain (not just an artifact of one lucky seed run)."""

from data.seed import SUSPECT_BATCH_COUNT


def test_row_counts_are_in_expected_range(db_connection):
    counts = {
        table: db_connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in [
            "suppliers", "press_lines", "material_lots", "production_batches",
            "decks", "orders", "warranty_claims",
        ]
    }
    assert counts["suppliers"] == 8
    assert counts["press_lines"] == 3
    assert counts["material_lots"] == 60
    assert counts["production_batches"] == 400
    assert 11000 <= counts["decks"] <= 13000
    assert 8000 <= counts["orders"] <= 10000
    assert 400 <= counts["warranty_claims"] <= 800


def test_suspect_lot_is_consumed_by_exactly_the_planted_batch_count(db_connection):
    rows = db_connection.execute("""
        SELECT lot_id, COUNT(DISTINCT batch_id) AS n
        FROM batch_material_lots
        WHERE lot_id IN (
            SELECT lot_id FROM material_lots WHERE material_type = 'maple_veneer'
        )
        GROUP BY lot_id
        HAVING COUNT(DISTINCT batch_id) = ?
    """, [SUSPECT_BATCH_COUNT]).fetchall()
    assert len(rows) == 1, "expected exactly one maple_veneer lot consumed by the planted batch count"


def test_suspect_lot_spans_exactly_two_press_lines():
    import duckdb
    from data.seed import DB_PATH

    con = duckdb.connect(str(DB_PATH), read_only=True)
    suspect_lot = con.execute("""
        SELECT lot_id FROM (
            SELECT lot_id, COUNT(DISTINCT batch_id) AS n
            FROM batch_material_lots
            GROUP BY lot_id
        ) WHERE n = 12
    """).fetchone()[0]
    lines = con.execute("""
        SELECT DISTINCT b.press_line_id
        FROM batch_material_lots bml
        JOIN production_batches b ON b.batch_id = bml.batch_id
        WHERE bml.lot_id = ?
    """, [suspect_lot]).fetchall()
    con.close()
    assert len(lines) == 2


def test_planted_signal_elevates_delamination_rate_at_matched_maturity(db_connection):
    suspect_batches = [
        r[0] for r in db_connection.execute("""
            SELECT batch_id FROM (
                SELECT batch_id, lot_id FROM batch_material_lots
            ) bml
            JOIN (
                SELECT lot_id FROM (
                    SELECT lot_id, COUNT(DISTINCT batch_id) AS n
                    FROM batch_material_lots GROUP BY lot_id
                ) WHERE n = 12
            ) suspect USING (lot_id)
        """).fetchall()
    ]
    assert len(suspect_batches) == 12

    placeholders = ", ".join("?" for _ in suspect_batches)

    def rate(condition: str) -> float:
        sql = f"""
            WITH mature AS (
                SELECT d.deck_id FROM decks d
                WHERE d.ship_date IS NOT NULL
                  AND DATE '2026-08-29' - d.ship_date >= 90
                  AND {condition}
            )
            SELECT COUNT(*) FILTER (WHERE wc.defect_type = 'delamination') * 100.0
                / NULLIF(COUNT(*), 0)
            FROM mature m
            LEFT JOIN warranty_claims wc ON wc.deck_id = m.deck_id
        """
        return db_connection.execute(sql, suspect_batches).fetchone()[0]

    suspect_rate = rate(f"d.batch_id IN ({placeholders})")
    baseline_rate = db_connection.execute("""
        WITH mature AS (
            SELECT d.deck_id, d.batch_id FROM decks d
            WHERE d.ship_date IS NOT NULL
              AND DATE '2026-08-29' - d.ship_date >= 90
        )
        SELECT COUNT(*) FILTER (WHERE wc.defect_type = 'delamination') * 100.0
            / NULLIF(COUNT(*), 0)
        FROM mature m
        LEFT JOIN warranty_claims wc ON wc.deck_id = m.deck_id
        WHERE m.batch_id NOT IN (%s)
    """ % placeholders, suspect_batches).fetchone()[0]

    assert suspect_rate > baseline_rate * 2, (
        f"expected the suspect lot's batches to show a clearly elevated "
        f"delamination rate at matched maturity: suspect={suspect_rate} "
        f"baseline={baseline_rate}"
    )
