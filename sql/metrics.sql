-- /sql/metrics.sql
-- Phase 4: Core analytics queries against the star schema.
-- Each query is self-contained and can be pasted into Power BI as a
-- custom SQL source, or run standalone in psql/DBeaver to sanity-check.
--
-- SCHEMA NOTE: fact_orders stores order_purchase_date_id (a surrogate key
-- into dim_date), not a raw order_purchase_timestamp column -- that column
-- was intentionally not persisted at load time. Queries that need the
-- purchase date join through dim_date instead. One consequence: dim_date
-- is day-granularity only, so "delivery time" below is computed as a
-- date-to-date difference (purchase day -> delivery timestamp's date),
-- not a precise timestamp-to-timestamp duration. This can be off by up to
-- ~1 day per order versus true elapsed time, since purchase time-of-day is
-- not available at day granularity. At ~96K delivered orders this noise
-- mostly averages out, but it's a real precision tradeoff worth naming if
-- asked about it -- a normal consequence of joining a date dimension
-- rather than carrying full timestamps in the fact table.

-- ============================================================
-- 1. MONTHLY REVENUE TREND
-- Revenue = sum of order_items.price (product revenue)
-- total_revenue = product revenue + freight
-- ============================================================

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


-- ============================================================
-- 2. TOP 10 PRODUCT CATEGORIES BY REVENUE
-- ============================================================
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


-- ============================================================
-- 3. REVENUE BY STATE (GEOGRAPHIC)
-- Customer's state, since that's the delivery destination.
-- ============================================================
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


-- ============================================================
-- 4. ORDER STATUS FUNNEL
-- Counts orders reaching each stage, using the null-timestamp signal
-- you deliberately preserved in Phase 2 (don't backfill these).
-- ============================================================
SELECT
    COUNT(*)                                                          AS total_orders,
    COUNT(*) FILTER (WHERE order_approved_at IS NOT NULL)             AS approved,
    COUNT(*) FILTER (WHERE order_delivered_carrier_date IS NOT NULL)  AS shipped,
    COUNT(*) FILTER (WHERE order_delivered_customer_date IS NOT NULL) AS delivered,
    COUNT(*) FILTER (WHERE order_status = 'canceled')                 AS canceled
FROM star.fact_orders;

-- Same funnel, expressed as % of total (useful for the dashboard funnel visual)
SELECT
    'approved'  AS stage, COUNT(*) AS n FROM star.fact_orders WHERE order_approved_at IS NOT NULL
UNION ALL
SELECT 'shipped', COUNT(*) FROM star.fact_orders WHERE order_delivered_carrier_date IS NOT NULL
UNION ALL
SELECT 'delivered', COUNT(*) FROM star.fact_orders WHERE order_delivered_customer_date IS NOT NULL
UNION ALL
SELECT 'canceled', COUNT(*) FROM star.fact_orders WHERE order_status = 'canceled';


-- ============================================================
-- 5. AVERAGE DELIVERY TIME
-- Purchase day -> delivery day, in days.
-- Day-granularity precision because purchase timestamp is not
-- persisted in fact_orders.
-- ============================================================

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


-- ============================================================
-- 6. REPEAT CUSTOMER RATE
-- Uses customer_unique_id (the actual person), not customer_id
-- (which is order-scoped) — this distinction matters, it's the
-- kind of detail worth calling out in an interview.
-- ============================================================
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


-- ============================================================
-- 7. AVERAGE ORDER VALUE (AOV) & PAYMENT MIX
-- Extra one — ties fact_payments in, gives you a payment-type
-- breakdown that's a nice business-facing cut for the Excel export.
-- ============================================================
SELECT
    fp.payment_type,
    COUNT(*)                                       AS num_payments,
    ROUND(AVG(fp.payment_value)::numeric, 2)        AS avg_payment_value,
    ROUND(AVG(fp.payment_installments)::numeric, 1) AS avg_installments,
    ROUND(SUM(fp.payment_value)::numeric, 2)        AS total_payment_value
FROM star.fact_payments fp
GROUP BY fp.payment_type
ORDER BY total_payment_value DESC;


-- ============================================================
-- 8. FREIGHT AS % OF PRICE (by category)
-- Extra one — surfaces categories where shipping cost eats into
-- revenue share, a good "so what" insight for stakeholder framing.
-- ============================================================
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