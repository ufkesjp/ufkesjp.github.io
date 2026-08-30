"""Deterministic synthetic data generator for Eval Boards.

Writes agent/data/eval_boards.duckdb from scratch. Every run with the same
SEED produces byte-identical data — this is a fixture, not a live system.

Plants exactly one discoverable signal: a single maple veneer lot
(SUSPECT_LOT_ID, printed at the end of the run) consumed by a dozen
production batches split across two of the three press lines. Decks from
those batches carry a delamination claim rate roughly 3x the fleet baseline
once measured at matched (90-day) field maturity. Nothing in the schema
flags the lot as suspect — it has to be found by traversing
claims -> decks -> batches -> consumed material lots and comparing rates.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import duckdb

SEED = 20260829
DB_PATH = Path(__file__).parent / "eval_boards.duckdb"

END_DATE = date(2026, 8, 29)
START_DATE = END_DATE - timedelta(days=18 * 30)

N_SUPPLIERS = 8
N_PRESS_LINES = 3
N_MATERIAL_LOTS = 60
N_BATCHES = 400
N_ACCOUNTS = 150
N_ORDERS = 9000
TARGET_DECKS = 12000
TARGET_CLAIMS = 600

SERIES = ["Pro", "Classic", "Cruiser", "Longboard"]
SERIES_WEIGHTS = [0.35, 0.30, 0.20, 0.15]
SHAPES = {
    "Pro": ["popsicle", "twin-tip"],
    "Classic": ["popsicle", "old-school"],
    "Cruiser": ["mini", "fish"],
    "Longboard": ["pintail", "drop-through"],
}
LENGTHS = {"Pro": 8.0, "Classic": 8.25, "Cruiser": 7.5, "Longboard": 9.5}

MATERIAL_TYPES = ["maple_veneer", "epoxy_resin", "grip_tape", "hardware", "paint"]
LOTS_PER_TYPE = {
    "maple_veneer": 14,
    "epoxy_resin": 12,
    "grip_tape": 12,
    "hardware": 12,
    "paint": 10,
}
SUPPLIERS_FOR_TYPE = {
    "maple_veneer": ["SUP01", "SUP02", "SUP03"],
    "epoxy_resin": ["SUP04", "SUP05"],
    "grip_tape": ["SUP05", "SUP06"],
    "hardware": ["SUP06", "SUP07", "SUP08"],
    "paint": ["SUP07", "SUP08"],
}
LOT_QUANTITY_RANGE = {
    "maple_veneer": (600, 1400),
    "epoxy_resin": (200, 600),
    "grip_tape": (300, 900),
    "hardware": (5000, 15000),
    "paint": (100, 400),
}
LOT_UNIT = {
    "maple_veneer": "sheets",
    "epoxy_resin": "liters",
    "grip_tape": "rolls",
    "hardware": "sets",
    "paint": "liters",
}

# Baseline probability a shipped deck has filed a delamination claim by the
# time it reaches 90 days of field maturity.
DELAM_BASELINE_P90 = 0.018
DELAM_SUSPECT_P90 = 0.055  # ~3x baseline

OTHER_DEFECT_P = {
    "chip": 0.014,
    "crack": 0.008,
    "hardware_failure": 0.011,
    "other": 0.006,
}

DEFECT_COST_RANGE = {
    "delamination": (120, 180),
    "chip": (20, 40),
    "crack": (60, 100),
    "hardware_failure": (30, 60),
    "other": (15, 50),
}

SUSPECT_BATCH_COUNT = 12
SUSPECT_PRESS_LINES = ["PL01", "PL02"]  # PL03 is deliberately clean: the red herring


def random_date(rng: random.Random, start: date, end: date) -> date:
    span = (end - start).days
    return start + timedelta(days=rng.randint(0, max(span, 0)))


def build_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("""
        CREATE TABLE suppliers (
            supplier_id VARCHAR PRIMARY KEY,
            name VARCHAR,
            country VARCHAR,
            onboarded_date DATE,
            quality_tier VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE press_lines (
            press_line_id VARCHAR PRIMARY KEY,
            name VARCHAR,
            location VARCHAR,
            install_date DATE
        )
    """)
    con.execute("""
        CREATE TABLE material_lots (
            lot_id VARCHAR PRIMARY KEY,
            supplier_id VARCHAR,
            material_type VARCHAR,
            received_date DATE,
            quantity DOUBLE,
            unit VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE production_batches (
            batch_id VARCHAR PRIMARY KEY,
            press_line_id VARCHAR,
            run_date DATE,
            series VARCHAR,
            deck_count INTEGER,
            status VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE batch_material_lots (
            batch_id VARCHAR,
            lot_id VARCHAR,
            quantity_used DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE decks (
            deck_id VARCHAR PRIMARY KEY,
            batch_id VARCHAR,
            series VARCHAR,
            shape VARCHAR,
            length_in DOUBLE,
            produced_at DATE,
            ship_date DATE
        )
    """)
    con.execute("""
        CREATE TABLE quality_inspections (
            inspection_id VARCHAR PRIMARY KEY,
            batch_id VARCHAR,
            inspector VARCHAR,
            inspection_date DATE,
            decks_inspected INTEGER,
            decks_passed INTEGER,
            defect_type VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE warranty_claims (
            claim_id VARCHAR PRIMARY KEY,
            deck_id VARCHAR,
            claim_date DATE,
            defect_type VARCHAR,
            resolution VARCHAR,
            warranty_cost DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE retail_accounts (
            account_id VARCHAR PRIMARY KEY,
            name VARCHAR,
            region VARCHAR,
            tier VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE orders (
            order_id VARCHAR PRIMARY KEY,
            account_id VARCHAR,
            batch_id VARCHAR,
            order_date DATE,
            ship_date DATE,
            status VARCHAR,
            deck_count INTEGER
        )
    """)


def gen_suppliers(rng: random.Random) -> list[tuple]:
    countries = ["USA", "Canada", "Mexico", "China", "Vietnam", "Germany"]
    rows = []
    for i in range(1, N_SUPPLIERS + 1):
        sid = f"SUP{i:02d}"
        onboarded = random_date(rng, START_DATE - timedelta(days=900), START_DATE)
        tier = rng.choices(["preferred", "standard"], weights=[0.4, 0.6])[0]
        rows.append((sid, f"Supplier {sid}", rng.choice(countries), onboarded, tier))
    return rows


def gen_press_lines() -> list[tuple]:
    return [
        ("PL01", "Press Line 1", "Portland, OR", date(2019, 3, 1)),
        ("PL02", "Press Line 2", "Portland, OR", date(2020, 6, 15)),
        ("PL03", "Press Line 3", "Reno, NV", date(2022, 1, 10)),
    ]


def gen_material_lots(rng: random.Random) -> list[tuple]:
    rows = []
    for material_type, count in LOTS_PER_TYPE.items():
        for i in range(count):
            lot_id = f"LOT-{material_type[:3].upper()}-{i + 1:03d}"
            supplier_id = rng.choice(SUPPLIERS_FOR_TYPE[material_type])
            received = random_date(
                rng, START_DATE - timedelta(days=30), END_DATE - timedelta(days=30)
            )
            qty_lo, qty_hi = LOT_QUANTITY_RANGE[material_type]
            quantity = round(rng.uniform(qty_lo, qty_hi), 1)
            rows.append(
                (lot_id, supplier_id, material_type, received, quantity, LOT_UNIT[material_type])
            )
    return rows


def gen_batches(rng: random.Random) -> list[tuple]:
    rows = []
    press_lines = ["PL01", "PL02", "PL03"]
    for i in range(1, N_BATCHES + 1):
        batch_id = f"B{i:04d}"
        run_date = random_date(rng, START_DATE, END_DATE - timedelta(days=1))
        press_line_id = rng.choice(press_lines)
        series = rng.choices(SERIES, weights=SERIES_WEIGHTS)[0]
        deck_count = rng.randint(25, 35)
        rows.append((batch_id, press_line_id, run_date, series, deck_count, "normal"))
    rows.sort(key=lambda r: r[2])
    return rows


def gen_batch_material_lots(
    rng: random.Random,
    batches: list[tuple],
    lots_by_type: dict[str, list[tuple]],
) -> tuple[list[tuple], list[str]]:
    """Returns (rows, suspect_batch_ids)."""
    # Reserved up front and excluded from the general random pool below, so
    # it ends up consumed by exactly the batches we assign it to explicitly.
    suspect_lot = lots_by_type["maple_veneer"][3]  # received early in the window
    suspect_lot_id, suspect_received = suspect_lot[0], suspect_lot[3]

    rows: list[tuple] = []
    for batch_id, press_line_id, run_date, series, deck_count, status in batches:
        for material_type in MATERIAL_TYPES:
            eligible = [lot for lot in lots_by_type[material_type] if lot[3] <= run_date]
            if material_type == "maple_veneer":
                eligible = [lot for lot in eligible if lot[0] != suspect_lot_id]
            if not eligible:
                eligible = lots_by_type[material_type][:1]
            lot = rng.choice(eligible)
            lot_id = lot[0]
            if material_type == "maple_veneer":
                qty_used = round(rng.uniform(20, 40), 1)
            elif material_type == "epoxy_resin":
                qty_used = round(rng.uniform(8, 18), 1)
            elif material_type == "grip_tape":
                qty_used = round(rng.uniform(10, 20), 1)
            elif material_type == "hardware":
                qty_used = round(rng.uniform(200, 400), 1)
            else:
                qty_used = round(rng.uniform(4, 10), 1)
            rows.append((batch_id, lot_id, qty_used))

    # Plant the signal: force a dozen batches onto the reserved maple_veneer
    # lot, split across two press lines so line-level aggregation stays clean.
    candidates_by_line: dict[str, list[str]] = {"PL01": [], "PL02": []}
    for batch_id, press_line_id, run_date, *_ in batches:
        if press_line_id in candidates_by_line and run_date > suspect_received + timedelta(days=14):
            candidates_by_line[press_line_id].append(batch_id)

    per_line = SUSPECT_BATCH_COUNT // 2
    suspect_batch_ids: list[str] = []
    for line in ("PL01", "PL02"):
        chosen = rng.sample(candidates_by_line[line], per_line)
        suspect_batch_ids.extend(chosen)

    suspect_set = set(suspect_batch_ids)
    # Overwrite each suspect batch's maple_veneer row with the suspect lot.
    new_rows = []
    for batch_id, lot_id, qty_used in rows:
        if batch_id in suspect_set and lot_id.startswith("LOT-MAP"):
            new_rows.append((batch_id, suspect_lot_id, round(rng.uniform(20, 40), 1)))
        else:
            new_rows.append((batch_id, lot_id, qty_used))

    return _cap_consumption_at_received_quantity(new_rows, lots_by_type), suspect_batch_ids


def _cap_consumption_at_received_quantity(
    rows: list[tuple], lots_by_type: dict[str, list[tuple]]
) -> list[tuple]:
    """A lot can't be consumed past what it received. If random draws pushed
    a lot's total quantity_used over its received quantity, scale that lot's
    rows down so total consumption caps at 90% (leaving a plausible unused
    remainder, consistent with what veneer_yield is meant to measure)."""
    lot_quantity = {lot[0]: lot[4] for lots in lots_by_type.values() for lot in lots}

    totals: dict[str, float] = {}
    for _batch_id, lot_id, qty_used in rows:
        totals[lot_id] = totals.get(lot_id, 0.0) + qty_used

    scale_factors: dict[str, float] = {}
    for lot_id, total in totals.items():
        cap = 0.9 * lot_quantity[lot_id]
        if total > cap:
            scale_factors[lot_id] = cap / total

    if not scale_factors:
        return rows
    return [
        (batch_id, lot_id, round(qty_used * scale_factors.get(lot_id, 1.0), 1))
        for batch_id, lot_id, qty_used in rows
    ]


def gen_decks(
    rng: random.Random, batches: list[tuple]
) -> list[tuple]:
    rows = []
    deck_counter = 1
    for batch_id, press_line_id, run_date, series, deck_count, status in batches:
        for _ in range(deck_count):
            deck_id = f"D{deck_counter:06d}"
            deck_counter += 1
            produced_at = run_date + timedelta(days=rng.randint(0, 3))
            shape = rng.choice(SHAPES[series])
            length_in = LENGTHS[series] + rng.uniform(-0.25, 0.25)

            ship_date = None
            if rng.random() < 0.92:
                offset = rng.randint(5, 40)
                candidate = produced_at + timedelta(days=offset)
                if candidate <= END_DATE:
                    ship_date = candidate

            rows.append(
                (deck_id, batch_id, series, shape, round(length_in, 2), produced_at, ship_date)
            )
    return rows


def gen_quality_inspections(rng: random.Random, batches: list[tuple]) -> list[tuple]:
    rows = []
    defect_pool = ["delamination", "chip", "crack", "hardware_failure", "other"]
    for i, (batch_id, press_line_id, run_date, series, deck_count, status) in enumerate(
        batches, start=1
    ):
        inspection_id = f"QI{i:04d}"
        inspection_date = run_date + timedelta(days=1)
        scrap = 0
        for _ in range(deck_count):
            if rng.random() < 0.04:
                scrap += 1
        decks_passed = deck_count - scrap
        defect_type = rng.choice(defect_pool) if scrap > 0 else None
        rows.append(
            (inspection_id, batch_id, f"inspector_{rng.randint(1, 6)}", inspection_date, deck_count, decks_passed, defect_type)
        )
    return rows


def gen_warranty_claims(
    rng: random.Random, decks: list[tuple], suspect_batch_ids: list[str]
) -> list[tuple]:
    suspect_set = set(suspect_batch_ids)
    rows = []
    claim_counter = 1
    for deck_id, batch_id, series, shape, length_in, produced_at, ship_date in decks:
        if ship_date is None:
            continue
        age_days = (END_DATE - ship_date).days
        if age_days <= 0:
            continue
        maturity_fraction = min(age_days, 90) / 90

        p_delam = (DELAM_SUSPECT_P90 if batch_id in suspect_set else DELAM_BASELINE_P90)
        probs = {"delamination": p_delam, **OTHER_DEFECT_P}
        scaled = {k: v * maturity_fraction for k, v in probs.items()}

        roll = rng.random()
        cumulative = 0.0
        fired_type = None
        for defect_type, p in scaled.items():
            cumulative += p
            if roll < cumulative:
                fired_type = defect_type
                break
        if fired_type is None:
            continue

        claim_offset = rng.randint(1, max(1, min(age_days, 90)))
        claim_date = ship_date + timedelta(days=claim_offset)
        resolution = rng.choices(
            ["replaced", "refunded", "denied", "pending"], weights=[0.5, 0.2, 0.2, 0.1]
        )[0]
        cost_lo, cost_hi = DEFECT_COST_RANGE[fired_type]
        cost = round(rng.uniform(cost_lo, cost_hi), 2)

        claim_id = f"WC{claim_counter:05d}"
        claim_counter += 1
        rows.append((claim_id, deck_id, claim_date, fired_type, resolution, cost))
    return rows


def gen_retail_accounts(rng: random.Random) -> list[tuple]:
    regions = ["Northeast", "Southeast", "Midwest", "Southwest", "West", "Pacific NW"]
    tiers = ["flagship", "standard", "online_only"]
    tier_weights = [0.15, 0.55, 0.30]
    rows = []
    for i in range(1, N_ACCOUNTS + 1):
        account_id = f"ACC{i:04d}"
        rows.append(
            (account_id, f"Retail Account {i}", rng.choice(regions), rng.choices(tiers, weights=tier_weights)[0])
        )
    return rows


def gen_orders(
    rng: random.Random, batches: list[tuple], accounts: list[tuple]
) -> list[tuple]:
    rows = []
    account_ids = [a[0] for a in accounts]
    # index batches by series for a plausible fulfillment match
    batches_by_series: dict[str, list[tuple]] = {s: [] for s in SERIES}
    for b in batches:
        batches_by_series[b[3]].append(b)

    for i in range(1, N_ORDERS + 1):
        order_id = f"ORD{i:05d}"
        series = rng.choices(SERIES, weights=SERIES_WEIGHTS)[0]
        candidates = batches_by_series[series]
        batch = rng.choice(candidates)
        batch_id, press_line_id, run_date, b_series, deck_count, status = batch
        order_date = random_date(rng, run_date, min(run_date + timedelta(days=60), END_DATE))
        deck_qty = rng.randint(1, 4)

        days_since_order = (END_DATE - order_date).days
        if days_since_order < 2:
            status = "pending"
            ship_date = None
        elif rng.random() < 0.03:
            status = "cancelled"
            ship_date = None
        else:
            status = "shipped"
            offset = rng.randint(1, 10)
            candidate = order_date + timedelta(days=offset)
            ship_date = candidate if candidate <= END_DATE else None
            if ship_date is None:
                status = "pending"

        rows.append(
            (order_id, rng.choice(account_ids), batch_id, order_date, ship_date, status, deck_qty)
        )
    return rows


def main() -> None:
    rng = random.Random(SEED)

    if DB_PATH.exists():
        DB_PATH.unlink()
    con = duckdb.connect(str(DB_PATH))
    build_schema(con)

    suppliers = gen_suppliers(rng)
    press_lines = gen_press_lines()
    material_lots = gen_material_lots(rng)
    batches = gen_batches(rng)

    lots_by_type: dict[str, list[tuple]] = {t: [] for t in MATERIAL_TYPES}
    for lot in material_lots:
        lots_by_type[lot[2]].append(lot)
    for t in lots_by_type:
        lots_by_type[t].sort(key=lambda lot: lot[3])

    batch_material_lots, suspect_batch_ids = gen_batch_material_lots(rng, batches, lots_by_type)
    decks = gen_decks(rng, batches)
    quality_inspections = gen_quality_inspections(rng, batches)
    warranty_claims = gen_warranty_claims(rng, decks, suspect_batch_ids)
    retail_accounts = gen_retail_accounts(rng)
    orders = gen_orders(rng, batches, retail_accounts)

    con.executemany("INSERT INTO suppliers VALUES (?, ?, ?, ?, ?)", suppliers)
    con.executemany("INSERT INTO press_lines VALUES (?, ?, ?, ?)", press_lines)
    con.executemany("INSERT INTO material_lots VALUES (?, ?, ?, ?, ?, ?)", material_lots)
    con.executemany("INSERT INTO production_batches VALUES (?, ?, ?, ?, ?, ?)", batches)
    con.executemany("INSERT INTO batch_material_lots VALUES (?, ?, ?)", batch_material_lots)
    con.executemany("INSERT INTO decks VALUES (?, ?, ?, ?, ?, ?, ?)", decks)
    con.executemany(
        "INSERT INTO quality_inspections VALUES (?, ?, ?, ?, ?, ?, ?)", quality_inspections
    )
    con.executemany("INSERT INTO warranty_claims VALUES (?, ?, ?, ?, ?, ?)", warranty_claims)
    con.executemany("INSERT INTO retail_accounts VALUES (?, ?, ?, ?)", retail_accounts)
    con.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)", orders)

    con.close()

    print(f"Wrote {DB_PATH}")
    print(f"  suppliers={len(suppliers)} press_lines={len(press_lines)} "
          f"material_lots={len(material_lots)} batches={len(batches)}")
    print(f"  decks={len(decks)} orders={len(orders)} claims={len(warranty_claims)}")
    suspect_lot_id = next(
        lot_id for b, lot_id, q in batch_material_lots if b == suspect_batch_ids[0]
    )
    print(f"  planted signal: lot={suspect_lot_id} suspect_batches={sorted(suspect_batch_ids)}")


if __name__ == "__main__":
    main()
