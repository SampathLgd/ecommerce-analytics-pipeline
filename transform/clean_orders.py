"""
Phase 2 - Transformation: clean and cast the orders table ahead of fact_orders
load in Phase 3.

Casts the four timestamp columns from raw `object` (string) to proper
datetime64. Per data-quality notes: null delivery/approval timestamps (~3%)
are expected — canceled or undelivered orders — and are intentionally left
null, not backfilled or dropped. This is the exact signal the order status
funnel metric (Phase 4) needs.

Output is written to /transform/clean_data/fact_orders_staging.parquet —
Phase 3's loader reads this file. This script does NOT touch the database
beyond reading raw_orders.

Usage:
    python transform/clean_orders.py
"""
from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "ingestion"))
from config import get_engine  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parent / "clean_data"
OUTPUT_PATH = OUTPUT_DIR / "fact_orders_staging.parquet"

TIMESTAMP_COLS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


def build_fact_orders_staging(orders: pd.DataFrame) -> pd.DataFrame:
    df = orders.copy()

    for col in TIMESTAMP_COLS:
        # errors="coerce" -> any unparseable string becomes NaT rather than
        # raising; the nulls we expect (approval/delivery) are already
        # genuine nulls in the source, not malformed strings.
        df[col] = pd.to_datetime(df[col], errors="coerce")

    df = df.drop_duplicates(subset=["order_id"])

    return df


def main() -> None:
    engine = get_engine()

    print("Loading raw_orders...")
    orders = pd.read_sql_table("raw_orders", engine, schema="raw")
    print(f"  raw_orders: {len(orders):,} rows")

    print("Casting timestamp columns to datetime64...")
    fact_orders_staging = build_fact_orders_staging(orders)

    for col in TIMESTAMP_COLS:
        n_null = fact_orders_staging[col].isna().sum()
        print(f"  {col:<32} dtype={fact_orders_staging[col].dtype}  "
              f"nulls={n_null:,} ({n_null / len(fact_orders_staging) * 100:.2f}%)")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fact_orders_staging.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nDone. Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()