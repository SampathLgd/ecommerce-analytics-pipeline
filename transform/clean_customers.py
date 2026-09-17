"""
Phase 2 - Transformation: build a dimension-ready customers DataFrame.

Reads raw.raw_customers and raw.raw_geolocation, dedupes geolocation (per the
data-quality notes: 26% duplicate rows, multiple submissions per zip code),
and attaches an approximate lat/long per customer via zip code prefix.

Output is written to /transform/clean_data/dim_customers.parquet — Phase 3's
loader reads this file and loads it into the star schema. This script does
NOT touch the database beyond reading raw tables.

Usage:
    python transform/clean_customers.py
"""
from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "ingestion"))
from config import get_engine  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parent / "clean_data"
OUTPUT_PATH = OUTPUT_DIR / "dim_customers.parquet"


def load_raw(engine) -> tuple[pd.DataFrame, pd.DataFrame]:
    customers = pd.read_sql_table("raw_customers", engine, schema="raw")
    geolocation = pd.read_sql_table("raw_geolocation", engine, schema="raw")
    return customers, geolocation


def dedupe_geolocation(geolocation: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse geolocation to one row per zip code prefix, averaging lat/lng
    across duplicate submissions for the same zip. This is the fix for the
    261,831 duplicate rows (26% of raw_geolocation) noted in Phase 2 profiling.
    """
    geo_clean = (
        geolocation
        .groupby("geolocation_zip_code_prefix", as_index=False)
        .agg(
            latitude=("geolocation_lat", "mean"),
            longitude=("geolocation_lng", "mean"),
        )
    )
    return geo_clean


def build_dim_customers(customers: pd.DataFrame, geo_clean: pd.DataFrame) -> pd.DataFrame:
    df = customers.merge(
        geo_clean,
        left_on="customer_zip_code_prefix",
        right_on="geolocation_zip_code_prefix",
        how="left",
    )

    df = df.rename(columns={
        "customer_zip_code_prefix": "zip_code_prefix",
        "customer_city": "city",
        "customer_state": "state",
    })

    dim = df[[
        "customer_id",
        "customer_unique_id",
        "zip_code_prefix",
        "city",
        "state",
        "latitude",
        "longitude",
    ]].copy()

    # customer_id is the order-level FK; customer_unique_id identifies the
    # actual person across multiple orders — keep both, don't collapse here.
    dim = dim.drop_duplicates(subset=["customer_id"])

    return dim


def main() -> None:
    engine = get_engine()

    print("Loading raw_customers and raw_geolocation...")
    customers, geolocation = load_raw(engine)

    print(f"  raw_customers:   {len(customers):,} rows")
    print(f"  raw_geolocation: {len(geolocation):,} rows")

    print("Deduping geolocation by zip code prefix...")
    geo_clean = dedupe_geolocation(geolocation)
    print(f"  -> {len(geo_clean):,} unique zip codes")

    print("Building dim_customers...")
    dim_customers = build_dim_customers(customers, geo_clean)

    n_missing_geo = dim_customers["latitude"].isna().sum()
    print(f"  -> {len(dim_customers):,} rows")
    print(f"  -> {n_missing_geo:,} customers with no geolocation match "
          f"({n_missing_geo / len(dim_customers) * 100:.2f}%) — zip prefix "
          f"not found in geolocation table, left as null")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dim_customers.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nDone. Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
