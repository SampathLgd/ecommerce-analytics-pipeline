"""
Phase 1 - Ingestion: load Olist's 9 raw CSVs into the Postgres `raw` schema, as-is.

No cleaning, joining, or transformation happens here — that's Phase 2. This
script's only job is: CSV -> raw table, byte-for-byte equivalent, so debugging
later never has to ask "was this broken by ingestion or by transformation?"

Re-runnable: each run drops and recreates the raw tables (if_exists="replace"),
so you can re-download fresher CSVs and just run it again.

Usage:
    python ingestion/load_olist_raw.py --data-dir ./data/olist

Expects the 9 Olist CSVs (from the Kaggle "Brazilian E-Commerce Public Dataset
by Olist") sitting in --data-dir with their original filenames.
"""
import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from config import get_engine

OLIST_FILES = {
    "olist_customers_dataset.csv": "raw_customers",
    "olist_geolocation_dataset.csv": "raw_geolocation",
    "olist_order_items_dataset.csv": "raw_order_items",
    "olist_order_payments_dataset.csv": "raw_order_payments",
    "olist_order_reviews_dataset.csv": "raw_order_reviews",
    "olist_orders_dataset.csv": "raw_orders",
    "olist_products_dataset.csv": "raw_products",
    "olist_sellers_dataset.csv": "raw_sellers",
    "product_category_name_translation.csv": "raw_category_translation",
}


def ensure_schema(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))


def load_csv_to_raw(engine, csv_path: Path, table_name: str) -> None:
    if not csv_path.exists():
        print(f"  [SKIP] {csv_path.name} not found at {csv_path}")
        return

    df = pd.read_csv(csv_path)
    df.to_sql(
        table_name,
        engine,
        schema="raw",
        if_exists="replace",
        index=False,
    )
    print(f"  [OK]   {csv_path.name:<45} -> raw.{table_name:<28} ({len(df):,} rows)")


def main(data_dir: str) -> None:
    data_path = Path(data_dir)
    engine = get_engine()

    print("Ensuring 'raw' schema exists...")
    ensure_schema(engine)

    print(f"Loading Olist CSVs from {data_path.resolve()}\n")
    for filename, table_name in OLIST_FILES.items():
        load_csv_to_raw(engine, data_path / filename, table_name)

    print("\nDone. Raw tables are in the 'raw' schema — untouched, unjoined, uncleaned.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Olist's 9 CSVs into Postgres raw schema.")
    parser.add_argument(
        "--data-dir",
        default="./data/olist",
        help="Directory containing the 9 Olist CSV files (default: ./data/olist)",
    )
    args = parser.parse_args()
    main(args.data_dir)
