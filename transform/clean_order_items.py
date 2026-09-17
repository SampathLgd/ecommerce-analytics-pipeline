"""
Phase 2/3 prep - Transformation: build staging DataFrame for fact_order_items.

No nulls or dtype issues per profiling (data_quality_notes.md) — the only
work here is casting shipping_limit_date to datetime64 for consistency with
the other fact staging tables.

Output is written to /transform/clean_data/fact_order_items_staging.parquet —
Phase 3's loader reads this file. This script does NOT touch the database
beyond reading raw_order_items.

Usage:
    python transform/clean_order_items.py
"""
from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "ingestion"))
from config import get_engine  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parent / "clean_data"
OUTPUT_PATH = OUTPUT_DIR / "fact_order_items_staging.parquet"


def build_fact_order_items_staging(order_items: pd.DataFrame) -> pd.DataFrame:
    df = order_items.copy()
    df["shipping_limit_date"] = pd.to_datetime(df["shipping_limit_date"], errors="coerce")

    # composite natural key: one row per (order_id, order_item_id)
    df = df.drop_duplicates(subset=["order_id", "order_item_id"])

    return df


def main() -> None:
    engine = get_engine()

    print("Loading raw_order_items...")
    order_items = pd.read_sql_table("raw_order_items", engine, schema="raw")
    print(f"  raw_order_items: {len(order_items):,} rows")

    print("Casting shipping_limit_date to datetime64...")
    fact_order_items_staging = build_fact_order_items_staging(order_items)
    print(f"  -> {len(fact_order_items_staging):,} rows")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fact_order_items_staging.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nDone. Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()