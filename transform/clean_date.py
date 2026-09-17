"""
Phase 2 - Transformation: build the date dimension.

Unlike the other dims, this isn't read from a raw table — it's a generated
date spine covering the full range of order activity, plus a buffer on both
ends so any delivery/estimated-delivery date that falls slightly outside the
purchase date range still finds a match in fact table joins.

Reads raw.raw_orders only to determine the date range to spine. Output is
written to /transform/clean_data/dim_date.parquet — Phase 3's loader reads
this file. This script does NOT touch the database beyond reading raw_orders.

Usage:
    python transform/clean_date.py
"""
from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "ingestion"))
from config import get_engine  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parent / "clean_data"
OUTPUT_PATH = OUTPUT_DIR / "dim_date.parquet"

BUFFER_DAYS = 60


def get_date_range(engine) -> tuple[pd.Timestamp, pd.Timestamp]:
    orders = pd.read_sql_table("raw_orders", engine, schema="raw")
    dates = pd.to_datetime(orders["order_purchase_timestamp"])
    return dates.min(), dates.max()


def build_dim_date(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    start = start.normalize() - pd.Timedelta(days=BUFFER_DAYS)
    end = end.normalize() + pd.Timedelta(days=BUFFER_DAYS)

    spine = pd.date_range(start=start, end=end, freq="D")

    dim = pd.DataFrame({"date": spine})
    dim["date_id"] = dim["date"].dt.strftime("%Y%m%d").astype(int)
    dim["year"] = dim["date"].dt.year
    dim["quarter"] = dim["date"].dt.quarter
    dim["month"] = dim["date"].dt.month
    dim["month_name"] = dim["date"].dt.month_name()
    dim["day"] = dim["date"].dt.day
    dim["day_of_week"] = dim["date"].dt.dayofweek
    dim["day_name"] = dim["date"].dt.day_name()
    dim["is_weekend"] = dim["day_of_week"].isin([5, 6])
    dim["year_month"] = dim["date"].dt.strftime("%Y-%m")

    dim = dim[[
        "date_id", "date", "year", "quarter", "month", "month_name",
        "day", "day_of_week", "day_name", "is_weekend", "year_month",
    ]]

    return dim


def main() -> None:
    engine = get_engine()

    print("Reading raw_orders to determine date range...")
    start, end = get_date_range(engine)
    print(f"  Order purchase range: {start.date()} to {end.date()}")

    print(f"Building dim_date with {BUFFER_DAYS}-day buffer on each end...")
    dim_date = build_dim_date(start, end)
    print(f"  -> {len(dim_date):,} rows "
          f"({dim_date['date'].min().date()} to {dim_date['date'].max().date()})")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dim_date.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nDone. Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
