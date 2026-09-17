"""
Phase 1 - Ingestion: small live REST API ingestion demo.

Pulls product data from the Fake Store API and lands it in raw.raw_api_products.
Kept intentionally small and separate from the Olist pipeline — this exists to
prove out live REST ingestion, NOT to feed the core star schema (do not blend
this data into fact/dim tables in Phase 3).

Usage:
    python ingestion/load_fake_store_api.py
"""
import sys

import pandas as pd
import requests
from sqlalchemy import text

from config import get_engine

API_URL = "https://fakestoreapi.com/products"


def fetch_products(url: str = API_URL) -> pd.DataFrame:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    df = pd.json_normalize(data)
    df["_ingested_at"] = pd.Timestamp.utcnow()
    return df


def ensure_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))


def main() -> None:
    engine = get_engine()
    ensure_schema(engine)

    print(f"Fetching products from {API_URL} ...")
    df = fetch_products()

    df.to_sql(
        "raw_api_products",
        engine,
        schema="raw",
        if_exists="replace",
        index=False,
    )
    print(f"[OK] raw.raw_api_products loaded ({len(df):,} rows)")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as e:
        print(f"[ERROR] Could not reach Fake Store API: {e}", file=sys.stderr)
        sys.exit(1)
