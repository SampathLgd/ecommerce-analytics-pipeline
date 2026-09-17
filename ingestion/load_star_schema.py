"""
Phase 3 - Load: idempotent loader for the star schema.

Reads the cleaned parquet files from transform/clean_data/ and upserts them
into star.* using ON CONFLICT DO UPDATE on the primary key. Safe to re-run —
re-running with the same or refreshed parquet files updates existing rows
rather than duplicating or failing.

Load order matters due to FKs: dims first, then fact_orders (referenced by
the other two facts), then fact_order_items and fact_payments.

Usage:
    python ingestion/load_star_schema.py
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

sys.path.append(str(Path(__file__).resolve().parent))
from config import get_engine  # noqa: E402

CLEAN_DATA_DIR = Path(__file__).resolve().parent.parent / "transform" / "clean_data"


def upsert_dataframe(
    engine: Engine,
    df: pd.DataFrame,
    table: str,
    pk_cols: list[str],
    schema: str = "star",
) -> None:
    """
    Upsert a DataFrame into a Postgres table using ON CONFLICT DO UPDATE on
    pk_cols. Batches rows to keep parameter counts sane on large tables.
    """
    if df.empty:
        print(f"  [SKIP] {table}: no rows to load")
        return

    df = df.replace({np.nan: None})
    cols = list(df.columns)
    update_cols = [c for c in cols if c not in pk_cols]

    col_list = ", ".join(cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    conflict_cols = ", ".join(pk_cols)

    if update_cols:
        update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        conflict_action = f"DO UPDATE SET {update_clause}"
    else:
        conflict_action = "DO NOTHING"

    stmt = text(
        f"INSERT INTO {schema}.{table} ({col_list}) VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict_cols}) {conflict_action}"
    )

    records = df.to_dict(orient="records")
    batch_size = 5000

    with engine.begin() as conn:
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            conn.execute(stmt, batch)

    print(f"  [OK] {schema}.{table}: upserted {len(df):,} rows")


def load_dim_date(engine: Engine) -> None:
    df = pd.read_parquet(CLEAN_DATA_DIR / "dim_date.parquet")
    upsert_dataframe(engine, df, "dim_date", pk_cols=["date_id"])


def load_dim_customers(engine: Engine) -> None:
    df = pd.read_parquet(CLEAN_DATA_DIR / "dim_customers.parquet")
    upsert_dataframe(engine, df, "dim_customers", pk_cols=["customer_id"])


def load_dim_products(engine: Engine) -> None:
    df = pd.read_parquet(CLEAN_DATA_DIR / "dim_products.parquet")
    upsert_dataframe(engine, df, "dim_products", pk_cols=["product_id"])


def load_dim_sellers(engine: Engine) -> None:
    df = pd.read_parquet(CLEAN_DATA_DIR / "dim_sellers.parquet")
    upsert_dataframe(engine, df, "dim_sellers", pk_cols=["seller_id"])


def load_fact_orders(engine: Engine) -> None:
    df = pd.read_parquet(CLEAN_DATA_DIR / "fact_orders_staging.parquet")

    df["order_purchase_date_id"] = (
        pd.to_datetime(df["order_purchase_timestamp"]).dt.strftime("%Y%m%d").astype(int)
    )

    df = df[[
        "order_id", "customer_id", "order_status", "order_purchase_date_id",
        "order_approved_at", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date",
    ]]

    upsert_dataframe(engine, df, "fact_orders", pk_cols=["order_id"])


def load_fact_order_items(engine: Engine) -> None:
    df = pd.read_parquet(CLEAN_DATA_DIR / "fact_order_items_staging.parquet")
    upsert_dataframe(engine, df, "fact_order_items", pk_cols=["order_id", "order_item_id"])


def load_fact_payments(engine: Engine) -> None:
    df = pd.read_parquet(CLEAN_DATA_DIR / "fact_payments_staging.parquet")
    upsert_dataframe(engine, df, "fact_payments", pk_cols=["order_id", "payment_sequential"])


def main() -> None:
    engine = get_engine()

    print("Loading dimensions...")
    load_dim_date(engine)
    load_dim_customers(engine)
    load_dim_products(engine)
    load_dim_sellers(engine)

    print("\nLoading facts...")
    load_fact_orders(engine)
    load_fact_order_items(engine)
    load_fact_payments(engine)

    print("\nDone. Star schema loaded — safe to re-run.")


if __name__ == "__main__":
    main()