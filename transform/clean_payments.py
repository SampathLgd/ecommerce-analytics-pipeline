"""
Phase 2/3 prep - Transformation: build staging DataFrame for fact_payments.

No nulls or dtype issues per profiling (data_quality_notes.md) — near
passthrough, just a dedup on the natural key.

Output is written to /transform/clean_data/fact_payments_staging.parquet —
Phase 3's loader reads this file. This script does NOT touch the database
beyond reading raw_order_payments.

Usage:
    python transform/clean_payments.py
"""
from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "ingestion"))
from config import get_engine  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parent / "clean_data"
OUTPUT_PATH = OUTPUT_DIR / "fact_payments_staging.parquet"


def build_fact_payments_staging(payments: pd.DataFrame) -> pd.DataFrame:
    df = payments.copy()

    # composite natural key: one row per (order_id, payment_sequential) —
    # orders can have multiple payment methods/installment records
    df = df.drop_duplicates(subset=["order_id", "payment_sequential"])

    return df


def main() -> None:
    engine = get_engine()

    print("Loading raw_order_payments...")
    payments = pd.read_sql_table("raw_order_payments", engine, schema="raw")
    print(f"  raw_order_payments: {len(payments):,} rows")

    fact_payments_staging = build_fact_payments_staging(payments)
    print(f"  -> {len(fact_payments_staging):,} rows after dedup")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fact_payments_staging.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nDone. Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()