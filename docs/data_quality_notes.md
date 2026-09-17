# Data Quality Notes — Raw Tables

Generated: 2026-09-17 19:48

Profiling run against `raw.*` staging tables, before any cleaning or transformation. Purpose: surface nulls, duplicates, and dtype issues that Phase 2's cleaning scripts need to handle.

## Summary

| Table | Rows | Cols | Duplicate Rows | Columns with Nulls |
|---|---|---|---|---|
| raw.raw_api_products | 20 | 9 | 0 | 0 |
| raw.raw_category_translation | 71 | 2 | 0 | 0 |
| raw.raw_customers | 99,441 | 5 | 0 | 0 |
| raw.raw_geolocation | 1,000,163 | 5 | 261,831 | 0 |
| raw.raw_order_items | 112,650 | 7 | 0 | 0 |
| raw.raw_order_payments | 103,886 | 5 | 0 | 0 |
| raw.raw_order_reviews | 99,224 | 7 | 0 | 2 |
| raw.raw_orders | 99,441 | 8 | 0 | 3 |
| raw.raw_products | 32,951 | 9 | 0 | 8 |
| raw.raw_sellers | 3,095 | 4 | 0 | 0 |

## Detail by table

### raw.raw_api_products

- Rows: 20 | Columns: 9 | Duplicate rows: 0
- No nulls found in any column.

### raw.raw_category_translation

- Rows: 71 | Columns: 2 | Duplicate rows: 0
- No nulls found in any column.

### raw.raw_customers

- Rows: 99,441 | Columns: 5 | Duplicate rows: 0
- No nulls found in any column.

### raw.raw_geolocation

- Rows: 1,000,163 | Columns: 5 | Duplicate rows: 261,831
- No nulls found in any column.

### raw.raw_order_items

- Rows: 112,650 | Columns: 7 | Duplicate rows: 0
- No nulls found in any column.

### raw.raw_order_payments

- Rows: 103,886 | Columns: 5 | Duplicate rows: 0
- No nulls found in any column.

### raw.raw_order_reviews

- Rows: 99,224 | Columns: 7 | Duplicate rows: 0

| Column | Null Count | Null % | Dtype |
|---|---|---|---|
| review_comment_title | 87,656 | 88.34% | object |
| review_comment_message | 58,247 | 58.7% | object |

### raw.raw_orders

- Rows: 99,441 | Columns: 8 | Duplicate rows: 0

| Column | Null Count | Null % | Dtype |
|---|---|---|---|
| order_delivered_customer_date | 2,965 | 2.98% | object |
| order_delivered_carrier_date | 1,783 | 1.79% | object |
| order_approved_at | 160 | 0.16% | object |

### raw.raw_products

- Rows: 32,951 | Columns: 9 | Duplicate rows: 0

| Column | Null Count | Null % | Dtype |
|---|---|---|---|
| product_category_name | 610 | 1.85% | object |
| product_name_lenght | 610 | 1.85% | float64 |
| product_description_lenght | 610 | 1.85% | float64 |
| product_photos_qty | 610 | 1.85% | float64 |
| product_weight_g | 2 | 0.01% | float64 |
| product_length_cm | 2 | 0.01% | float64 |
| product_height_cm | 2 | 0.01% | float64 |
| product_width_cm | 2 | 0.01% | float64 |

### raw.raw_sellers

- Rows: 3,095 | Columns: 4 | Duplicate rows: 0
- No nulls found in any column.

## Notes for Phase 2 cleaning

- (fill in manually after reviewing the tables above — e.g. which nulls are expected/acceptable vs. which need imputation or filtering, any dtype casts needed before joining, dedupe strategy per table)
## Cleaning strategy (filled in after review)

- **raw_geolocation**: 261,831 duplicate rows (26% of table) — real issue, dedupe on
  (zip_code_prefix, lat, lng) or just `.drop_duplicates()` before building any
  geo lookup. Multiple submissions per zip code, not meaningful variation.
- **raw_order_reviews**: null comment title/message (88% / 59%) — expected, not a
  defect. Most reviews are star-rating-only. Leave as null; do not impute.
- **raw_orders**: null delivery/approval timestamps (~3%) — expected. These are
  canceled or undelivered orders. Leave as null — this is exactly the signal the
  order status funnel metric needs, don't backfill or drop these rows.
- **raw_products**: ~610 rows (1.85%) missing category + description metadata.
  Decision: bucket as `category = 'unknown'` rather than dropping — these products
  still appear in order_items and dropping them would silently lose revenue from
  the fact tables. The 2 rows missing physical dimensions are negligible; leave
  null unless a specific downstream calc (e.g. freight estimation) requires them.
- **dtype casts needed before Phase 3 load**: all date/timestamp columns above
  are currently `object` (loaded as raw strings) — cast to proper `datetime64`
  during transformation, not during ingestion.
- No table other than geolocation has duplicate rows; no further dedup needed.
