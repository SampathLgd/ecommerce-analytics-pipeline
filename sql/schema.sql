-- Star schema for E-Commerce Sales Analytics Pipeline
-- 4 dimensions + 3 facts, as scoped in Phase 3. Intentionally not
-- normalized further (e.g. no separate geography dim) — see Implementation
-- Details guardrails.

CREATE SCHEMA IF NOT EXISTS star;

-- ============================================================
-- DIMENSIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS star.dim_date (
    date_id         INTEGER PRIMARY KEY,        -- YYYYMMDD surrogate key
    date            DATE NOT NULL UNIQUE,
    year            SMALLINT NOT NULL,
    quarter         SMALLINT NOT NULL,
    month           SMALLINT NOT NULL,
    month_name      VARCHAR(20) NOT NULL,
    day             SMALLINT NOT NULL,
    day_of_week     SMALLINT NOT NULL,          -- 0=Monday
    day_name        VARCHAR(20) NOT NULL,
    is_weekend      BOOLEAN NOT NULL,
    year_month      VARCHAR(7) NOT NULL         -- 'YYYY-MM'
);

CREATE TABLE IF NOT EXISTS star.dim_customers (
    customer_id         VARCHAR(64) PRIMARY KEY,   -- order-level FK
    customer_unique_id  VARCHAR(64) NOT NULL,      -- identifies the person across orders
    zip_code_prefix     INTEGER,
    city                VARCHAR(100),
    state               CHAR(2),
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_dim_customers_unique_id ON star.dim_customers (customer_unique_id);

CREATE TABLE IF NOT EXISTS star.dim_products (
    product_id                      VARCHAR(64) PRIMARY KEY,
    product_category_name           VARCHAR(100) NOT NULL,   -- 'unknown' if missing
    product_category_name_english   VARCHAR(100) NOT NULL,   -- 'unknown' if missing
    product_name_length             SMALLINT,
    product_description_length      INTEGER,
    product_photos_qty              SMALLINT,
    product_weight_g                INTEGER,
    product_length_cm               INTEGER,
    product_height_cm               INTEGER,
    product_width_cm                INTEGER
);

CREATE TABLE IF NOT EXISTS star.dim_sellers (
    seller_id           VARCHAR(64) PRIMARY KEY,
    zip_code_prefix     INTEGER,
    city                VARCHAR(100),
    state               CHAR(2)
);

-- ============================================================
-- FACTS
-- ============================================================

CREATE TABLE IF NOT EXISTS star.fact_orders (
    order_id                        VARCHAR(64) PRIMARY KEY,
    customer_id                     VARCHAR(64) NOT NULL REFERENCES star.dim_customers (customer_id),
    order_status                    VARCHAR(20) NOT NULL,
    order_purchase_date_id          INTEGER REFERENCES star.dim_date (date_id),
    order_approved_at               TIMESTAMP,
    order_delivered_carrier_date    TIMESTAMP,
    order_delivered_customer_date   TIMESTAMP,
    order_estimated_delivery_date   TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fact_orders_customer ON star.fact_orders (customer_id);
CREATE INDEX IF NOT EXISTS idx_fact_orders_purchase_date ON star.fact_orders (order_purchase_date_id);
CREATE INDEX IF NOT EXISTS idx_fact_orders_status ON star.fact_orders (order_status);

CREATE TABLE IF NOT EXISTS star.fact_order_items (
    order_id             VARCHAR(64) NOT NULL REFERENCES star.fact_orders (order_id),
    order_item_id        SMALLINT NOT NULL,
    product_id           VARCHAR(64) NOT NULL REFERENCES star.dim_products (product_id),
    seller_id            VARCHAR(64) NOT NULL REFERENCES star.dim_sellers (seller_id),
    shipping_limit_date  TIMESTAMP,
    price                NUMERIC(12, 2) NOT NULL,
    freight_value        NUMERIC(12, 2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);
CREATE INDEX IF NOT EXISTS idx_fact_order_items_product ON star.fact_order_items (product_id);
CREATE INDEX IF NOT EXISTS idx_fact_order_items_seller ON star.fact_order_items (seller_id);

CREATE TABLE IF NOT EXISTS star.fact_payments (
    order_id             VARCHAR(64) NOT NULL REFERENCES star.fact_orders (order_id),
    payment_sequential   SMALLINT NOT NULL,
    payment_type         VARCHAR(20) NOT NULL,
    payment_installments SMALLINT NOT NULL,
    payment_value        NUMERIC(12, 2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);
CREATE INDEX IF NOT EXISTS idx_fact_payments_type ON star.fact_payments (payment_type);