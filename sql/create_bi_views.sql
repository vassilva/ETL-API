-- BI semantic layer for Power BI (schema bi).
--
-- Thin, read-only views over the ETL target tables. They only rename,
-- select and handle NULLs: every business rule stays in the ETL (tested by
-- the ETL suite) and every aggregation stays in the report (DAX). Nothing is
-- materialized and no base table is changed.
--
-- Idempotent: CREATE SCHEMA IF NOT EXISTS + CREATE OR REPLACE VIEW, in one
-- transaction. Run manually after sql/create_tables.sql, e.g.:
--   psql -h <host> -p <port> -d <database> -U <user> -f sql/create_bi_views.sql
--
-- Semantics (the data has no dates and no order status):
--   quantity in carts  = units currently in customer carts, NOT units sold
--   cart values        = value of cart lines, NOT confirmed revenue
--   stock              = current product stock snapshot, NOT history
-- Stock lives only on bi.dim_product: never aggregate it through cart lines.

BEGIN;

CREATE SCHEMA IF NOT EXISTS bi;

-- Grain: one product line inside one cart (cart_id, item_position).
-- The inner join to carts only adds user_id; every cart line has its cart
-- (cart_items.cart_id is NOT NULL with a foreign key to carts).
CREATE OR REPLACE VIEW bi.fact_cart_item AS
SELECT
    ci.cart_id,
    ci.item_position,
    c.user_id,
    ci.product_id,
    ci.quantity,
    ci.price                                AS unit_price,
    ci.total                                AS gross_value,
    ci.discounted_total                     AS discounted_value,
    ci.total - ci.discounted_total          AS discount_value,
    ci.discount_percentage
FROM public.cart_items AS ci
JOIN public.carts AS c
    ON c.cart_id = ci.cart_id;

-- Grain: one product (current snapshot). product_name is the single display
-- name (ETL rule: title + ' - RP'). discounted_price is intentionally not
-- exposed: monetary KPIs come from the cart-line values.
CREATE OR REPLACE VIEW bi.dim_product AS
SELECT
    p.product_id,
    p.product_name,
    p.category,
    COALESCE(p.brand, '(No brand)')         AS brand,
    p.price,
    p.discount_percentage,
    p.rating,
    p.stock,
    p.availability_status,
    p.sku
FROM public.products AS p;

-- Grain: one customer (user). Personal contact data (email, phone) and the
-- separate first/last name columns are intentionally not exposed.
CREATE OR REPLACE VIEW bi.dim_customer AS
SELECT
    u.user_id,
    u.full_name,
    u.city,
    u.state,
    u.country,
    u.department
FROM public.users AS u;

COMMENT ON SCHEMA bi IS 'Read-only BI semantic layer (Power BI); thin views over the ETL target tables';
COMMENT ON VIEW bi.fact_cart_item IS 'One product line inside one cart. Cart values are not confirmed revenue';
COMMENT ON VIEW bi.dim_product IS 'One product, current snapshot';
COMMENT ON VIEW bi.dim_customer IS 'One customer; no email or phone';
COMMENT ON COLUMN bi.fact_cart_item.quantity IS 'Units currently in customer carts (not units sold)';
COMMENT ON COLUMN bi.dim_product.stock IS 'Current stock snapshot (not historical); never aggregate through cart lines';

COMMIT;
