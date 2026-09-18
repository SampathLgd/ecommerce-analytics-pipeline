"""
Phase 4 verification: run every query in sql/metrics.sql against the live
star schema, print results, and flag anything structurally off before
declaring Phase 4 done.

This is a read-only diagnostic — it does not touch the database.

Usage (from repo root, with venv active and POSTGRES_PORT set):
    python verify_metrics.py
"""
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parent / "ingestion"))
from config import get_engine  # noqa: E402

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 120)

QUERIES = {
    "1. Monthly revenue trend": """
        SELECT
            dd.year_month                                          AS order_month,
            COUNT(DISTINCT fo.order_id)                            AS num_orders,
            ROUND(SUM(foi.price)::numeric, 2)                     AS product_revenue,
            ROUND(SUM(foi.price + foi.freight_value)::numeric, 2) AS total_revenue
        FROM star.fact_orders fo
        JOIN star.dim_date dd
            ON dd.date_id = fo.order_purchase_date_id
        JOIN star.fact_order_items foi
            ON foi.order_id = fo.order_id
        WHERE fo.order_status NOT IN ('canceled', 'unavailable')
        GROUP BY dd.year_month
        ORDER BY dd.year_month;
    """,
    "2. Top 10 categories by revenue": """
        SELECT
            dp.product_category_name_english,
            COUNT(*)                                     AS items_sold,
            ROUND(SUM(foi.price)::numeric, 2)            AS category_revenue,
            ROUND(AVG(foi.price)::numeric, 2)            AS avg_item_price
        FROM star.fact_order_items foi
        JOIN star.dim_products dp ON dp.product_id = foi.product_id
        JOIN star.fact_orders fo ON fo.order_id = foi.order_id
        WHERE fo.order_status NOT IN ('canceled', 'unavailable')
        GROUP BY dp.product_category_name_english
        ORDER BY category_revenue DESC
        LIMIT 10;
    """,
    "3. Revenue by state": """
        SELECT
            dc.state,
            COUNT(DISTINCT fo.order_id)                   AS num_orders,
            ROUND(SUM(foi.price)::numeric, 2)             AS state_revenue,
            ROUND(SUM(foi.price)::numeric / COUNT(DISTINCT fo.order_id), 2) AS revenue_per_order
        FROM star.fact_orders fo
        JOIN star.dim_customers dc ON dc.customer_id = fo.customer_id
        JOIN star.fact_order_items foi ON foi.order_id = fo.order_id
        WHERE fo.order_status NOT IN ('canceled', 'unavailable')
        GROUP BY dc.state
        ORDER BY state_revenue DESC;
    """,
    "4. Order status funnel": """
        SELECT 'approved' AS stage, COUNT(*) AS n FROM star.fact_orders WHERE order_approved_at IS NOT NULL
        UNION ALL
        SELECT 'shipped', COUNT(*) FROM star.fact_orders WHERE order_delivered_carrier_date IS NOT NULL
        UNION ALL
        SELECT 'delivered', COUNT(*) FROM star.fact_orders WHERE order_delivered_customer_date IS NOT NULL
        UNION ALL
        SELECT 'canceled', COUNT(*) FROM star.fact_orders WHERE order_status = 'canceled';
    """,
    "5. Avg delivery time": """
        SELECT
            ROUND(
                AVG(
                    fo.order_delivered_customer_date::date - dd.date
                ),
                2
            ) AS avg_delivery_days,

            ROUND(
                PERCENTILE_CONT(0.5) WITHIN GROUP (
                    ORDER BY (
                        fo.order_delivered_customer_date::date - dd.date
                    )
                )::numeric,
                2
            ) AS median_delivery_days,

            ROUND(
                AVG(
                    fo.order_estimated_delivery_date::date
                    - fo.order_delivered_customer_date::date
                ),
                2
            ) AS avg_days_early_or_late

        FROM star.fact_orders fo
        JOIN star.dim_date dd
            ON dd.date_id = fo.order_purchase_date_id
        WHERE fo.order_delivered_customer_date IS NOT NULL;
    """,
    "6. Repeat customer rate": """
        WITH orders_per_person AS (
            SELECT
                dc.customer_unique_id,
                COUNT(DISTINCT fo.order_id) AS num_orders
            FROM star.fact_orders fo
            JOIN star.dim_customers dc ON dc.customer_id = fo.customer_id
            WHERE fo.order_status NOT IN ('canceled', 'unavailable')
            GROUP BY dc.customer_unique_id
        )
        SELECT
            COUNT(*) FILTER (WHERE num_orders > 1)                             AS repeat_customers,
            COUNT(*)                                                           AS total_customers,
            ROUND(100.0 * COUNT(*) FILTER (WHERE num_orders > 1) / COUNT(*), 2) AS repeat_customer_rate_pct
        FROM orders_per_person;
    """,
    "7. Payment mix": """
        SELECT
            fp.payment_type,
            COUNT(*)                                       AS num_payments,
            ROUND(AVG(fp.payment_value)::numeric, 2)        AS avg_payment_value,
            ROUND(AVG(fp.payment_installments)::numeric, 1) AS avg_installments,
            ROUND(SUM(fp.payment_value)::numeric, 2)        AS total_payment_value
        FROM star.fact_payments fp
        GROUP BY fp.payment_type
        ORDER BY total_payment_value DESC;
    """,
    "8. Freight % of price by category": """
        SELECT
            dp.product_category_name_english,
            ROUND(SUM(foi.price)::numeric, 2)                        AS product_revenue,
            ROUND(SUM(foi.freight_value)::numeric, 2)                AS freight_cost,
            ROUND(100.0 * SUM(foi.freight_value) / NULLIF(SUM(foi.price), 0), 2) AS freight_pct_of_price
        FROM star.fact_order_items foi
        JOIN star.dim_products dp ON dp.product_id = foi.product_id
        GROUP BY dp.product_category_name_english
        ORDER BY freight_pct_of_price DESC
        LIMIT 15;
    """,
}


def run_query(engine, name: str, sql: str) -> pd.DataFrame:
    return pd.read_sql(text(sql), engine)


def sanity_checks(engine) -> list[str]:
    """Independent checks that don't rely on the metrics queries themselves,
    so a bug shared between a metric query and its check won't hide a problem."""
    issues = []
    with engine.connect() as conn:
        total_order_items = conn.execute(text("SELECT COUNT(*) FROM star.fact_order_items")).scalar()
        total_orders = conn.execute(text("SELECT COUNT(*) FROM star.fact_orders")).scalar()
        total_customers = conn.execute(text("SELECT COUNT(DISTINCT customer_unique_id) FROM star.dim_customers")).scalar()
        raw_revenue = conn.execute(text("SELECT ROUND(SUM(price)::numeric, 2) FROM star.fact_order_items")).scalar()
        orphan_items = conn.execute(text(
            "SELECT COUNT(*) FROM star.fact_order_items foi "
            "LEFT JOIN star.fact_orders fo ON fo.order_id = foi.order_id "
            "WHERE fo.order_id IS NULL"
        )).scalar()

    if orphan_items and orphan_items > 0:
        issues.append(f"{orphan_items:,} fact_order_items rows have no matching fact_orders row (FK should have prevented this)")

    print(f"\n[reference] fact_order_items rows: {total_order_items:,}")
    print(f"[reference] fact_orders rows: {total_orders:,}")
    print(f"[reference] distinct customer_unique_id: {total_customers:,}")
    print(f"[reference] raw SUM(price) across all order_items (no status filter): R$ {raw_revenue:,.2f}")

    return issues


def main() -> None:
    engine = get_engine()
    all_issues = []

    print("=" * 70)
    print("Running independent sanity checks first (no dependency on metrics.sql)")
    print("=" * 70)
    all_issues.extend(sanity_checks(engine))

    for name, sql in QUERIES.items():
        print("\n" + "=" * 70)
        print(name)
        print("=" * 70)
        try:
            df = run_query(engine, name, sql)
        except Exception as e:
            print(f"[ERROR] Query failed: {e}")
            all_issues.append(f"{name}: query raised an exception — {e}")
            continue

        if df.empty:
            print("[WARNING] Query returned zero rows.")
            all_issues.append(f"{name}: returned zero rows")
            continue

        print(df.to_string(index=False))

        # Lightweight per-query red flags
        if "1." in name and (df["total_revenue"] <= 0).any():
            all_issues.append(f"{name}: found a month with zero/negative revenue")
        if "4." in name:
            approved = df.loc[df["stage"] == "approved", "n"].iloc[0]
            shipped = df.loc[df["stage"] == "shipped", "n"].iloc[0]
            delivered = df.loc[df["stage"] == "delivered", "n"].iloc[0]
            if not (approved >= shipped >= delivered):
                all_issues.append(
                    f"{name}: funnel is not monotonically decreasing "
                    f"(approved={approved}, shipped={shipped}, delivered={delivered}) — check filters"
                )
        if "6." in name:
            rate = df["repeat_customer_rate_pct"].iloc[0]
            if not (0 < rate < 100):
                all_issues.append(f"{name}: repeat_customer_rate_pct={rate} is out of plausible range")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    if all_issues:
        print(f"{len(all_issues)} issue(s) found — review before calling Phase 4 done:\n")
        for i in all_issues:
            print(f"  - {i}")
    else:
        print("No structural issues found. All 8 queries returned data and passed sanity checks.")


if __name__ == "__main__":
    main()