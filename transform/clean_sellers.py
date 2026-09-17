"""
Phase 2 - Transformation: build a dimension-ready sellers DataFrame.

Reads raw.raw_sellers. No nulls or duplicates per profiling (data_quality_notes.md),
so this is close to a passthrough — just column renames for consistency with the
star schema naming (zip_code_prefix, city, state matching dim_customers).

Output is written to /transform/clean_data/dim_sellers.parquet — Phase 3's
loader reads this file. This script does NOT touch the database beyond
reading raw tables.

Usage:
    python transform/clean_sellers.py
"""
from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "ingestion"))
from config import get_engine  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parent / "clean_data"
OUTPUT_PATH = OUTPUT_DIR / "dim_sellers.parquet"


def build_dim_sellers(sellers: pd.DataFrame) -> pd.DataFrame:
    df = sellers.rename(columns={
        "seller_zip_code_prefix": "zip_code_prefix",
        "seller_city": "city",
        "seller_state": "state",
    })

    dim = df[[
        "seller_id",
        "zip_code_prefix",
        "city",
        "state",
    ]].copy()

    dim = dim.drop_duplicates(subset=["seller_id"])

    return dim


def main() -> None:
    engine = get_engine()

    print("Loading raw_sellers...")
    sellers = pd.read_sql_table("raw_sellers", engine, schema="raw")
    print(f"  raw_sellers: {len(sellers):,} rows")

    print("Building dim_sellers...")
    dim_sellers = build_dim_sellers(sellers)
    print(f"  -> {len(dim_sellers):,} rows")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dim_sellers.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nDone. Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()