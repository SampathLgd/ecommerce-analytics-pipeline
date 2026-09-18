-- ============================================================
-- Dashboard views for Power BI
-- Corrected 2026-09-18: earlier draft referenced dc.customer_key /
-- dc.customer_state (never existed) and order_shipped_at (should be
-- order_delivered_carrier_date). Column names below match sql/schema.sql.
-- ============================================================

CREATE OR REPLACE VIEW star.vw_monthly_revenue AS
SELECT
    dd.year_month AS order_month,
    COUNT(DISTINCT fo.order_id) AS num_orders,
    ROUND(SUM(foi.price)::numeric, 2) AS product_revenue,
    ROUND(
        (SUM(foi.price) + SUM(foi.freight_value))::numeric,
        2
    ) AS total_revenue
FROM star.fact_orders fo
JOIN star.fact_order_items foi
    ON fo.order_id = foi.order_id
JOIN star.dim_date dd
    ON dd.date_id = fo.order_purchase_date_id
GROUP BY dd.year_month
ORDER BY dd.year_month;


CREATE OR REPLACE VIEW star.vw_category_revenue AS
SELECT
    dp.product_category_name_english,
    COUNT(*) AS items_sold,
    ROUND(SUM(foi.price)::numeric, 2) AS category_revenue,
    ROUND(AVG(foi.price)::numeric, 2) AS avg_item_price
FROM star.fact_order_items foi
JOIN star.dim_products dp
    ON dp.product_id = foi.product_id
GROUP BY dp.product_category_name_english
ORDER BY category_revenue DESC;


CREATE OR REPLACE VIEW star.vw_state_revenue AS
SELECT
    dc.state,
    COUNT(DISTINCT fo.order_id) AS num_orders,
    ROUND(SUM(foi.price)::numeric, 2) AS state_revenue,
    ROUND(
        (SUM(foi.price) / COUNT(DISTINCT fo.order_id))::numeric,
        2
    ) AS revenue_per_order
FROM star.fact_orders fo
JOIN star.fact_order_items foi
    ON fo.order_id = foi.order_id
JOIN star.dim_customers dc
    ON dc.customer_id = fo.customer_id
GROUP BY dc.state
ORDER BY state_revenue DESC;


CREATE OR REPLACE VIEW star.vw_order_funnel AS
SELECT
    'approved' AS stage,
    COUNT(*) AS n
FROM star.fact_orders
WHERE order_approved_at IS NOT NULL

UNION ALL

SELECT
    'shipped',
    COUNT(*)
FROM star.fact_orders
WHERE order_delivered_carrier_date IS NOT NULL

UNION ALL

SELECT
    'delivered',
    COUNT(*)
FROM star.fact_orders
WHERE order_delivered_customer_date IS NOT NULL

UNION ALL

SELECT
    'canceled',
    COUNT(*)
FROM star.fact_orders
WHERE order_status = 'canceled';
