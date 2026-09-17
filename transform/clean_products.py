"""
Phase 2 - Transformation: build a dimension-ready products DataFrame.

Reads raw.raw_products and raw.raw_category_translation, joins in English
category names, and fills missing category/description metadata as 'unknown'
rather than dropping rows (per data-quality notes: these products still appear
in order_items, so dropping them would silently lose revenue from the fact
tables downstream).

Output is written to /transform/clean_data/dim_products.parquet — Phase 3's
loader reads this file. This script does NOT touch the database beyond
reading raw tables.

Usage:
    python transform/clean_products.py
"""
from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent / "ingestion"))
from config import get_engine  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parent / "clean_data"
OUTPUT_PATH = OUTPUT_DIR / "dim_products.parquet"


def load_raw(engine) -> tuple[pd.DataFrame, pd.DataFrame]:
    products = pd.read_sql_table("raw_products", engine, schema="raw")
    translation = pd.read_sql_table("raw_category_translation", engine, schema="raw")
    return products, translation


def build_dim_products(products: pd.DataFrame, translation: pd.DataFrame) -> pd.DataFrame:
    df = products.merge(
        translation,
        on="product_category_name",
        how="left",
    )

    # ~610 rows (1.85%) missing category_name entirely -> no translation match
    # either. Bucket both as 'unknown' per data-quality notes, don't drop —
    # these rows still appear in order_items and dropping them would silently
    # lose revenue from the fact tables.
    df["product_category_name"] = df["product_category_name"].fillna("unknown")
    df["product_category_name_english"] = df["product_category_name_english"].fillna("unknown")

    df = df.rename(columns={
        "product_name_lenght": "product_name_length",
        "product_description_lenght": "product_description_length",
    })

    dim = df[[
        "product_id",
        "product_category_name",
        "product_category_name_english",
        "product_name_length",
        "product_description_length",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]].copy()

    dim = dim.drop_duplicates(subset=["product_id"])

    return dim


def main() -> None:
    engine = get_engine()

    print("Loading raw_products and raw_category_translation...")
    products, translation = load_raw(engine)

    print(f"  raw_products:               {len(products):,} rows")
    print(f"  raw_category_translation:   {len(translation):,} rows")

    print("Building dim_products...")
    dim_products = build_dim_products(products, translation)

    n_unknown_category = (dim_products["product_category_name"] == "unknown").sum()
    n_missing_dims = dim_products["product_weight_g"].isna().sum()

    print(f"  -> {len(dim_products):,} rows")
    print(f"  -> {n_unknown_category:,} products bucketed as 'unknown' category "
          f"({n_unknown_category / len(dim_products) * 100:.2f}%)")
    print(f"  -> {n_missing_dims:,} products missing physical dimensions "
          f"(left as null, negligible per data-quality notes)")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dim_products.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nDone. Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()