-- ETL target schema (PostgreSQL).
--
-- Mirrors the tables the load layer writes to. Non-destructive: every
-- statement is CREATE ... IF NOT EXISTS, so running it against an existing
-- database changes nothing. Nothing is dropped or truncated.
--
-- The UPSERTs in src/load depend on these keys:
--   users.user_id, products.product_id, carts.cart_id  (PRIMARY KEY)
--   cart_items (cart_id, item_position)                 (UNIQUE)

CREATE TABLE IF NOT EXISTS users (
    user_id         INTEGER PRIMARY KEY,
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    full_name       VARCHAR(200),
    email           VARCHAR(255),
    phone           VARCHAR(50),
    city            VARCHAR(100),
    state           VARCHAR(100),
    country         VARCHAR(100),
    company_name    VARCHAR(255),
    department      VARCHAR(150)
);

CREATE TABLE IF NOT EXISTS products (
    product_id           INTEGER PRIMARY KEY,
    product_name         VARCHAR(255),
    category             VARCHAR(150),
    price                NUMERIC(10, 2),
    discount_percentage  NUMERIC(5, 2),
    discounted_price     NUMERIC(10, 2),
    rating               NUMERIC(4, 2),
    stock                INTEGER,
    brand                VARCHAR(150),
    sku                  VARCHAR(100),
    availability_status  VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS carts (
    cart_id           INTEGER PRIMARY KEY,
    user_id           INTEGER NOT NULL,
    total             NUMERIC(12, 2),
    discounted_total  NUMERIC(12, 2),
    total_products    INTEGER,
    total_quantity    INTEGER,

    CONSTRAINT fk_carts_user
        FOREIGN KEY (user_id) REFERENCES users (user_id)
);

CREATE TABLE IF NOT EXISTS cart_items (
    cart_item_id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cart_id              INTEGER NOT NULL,
    item_position        INTEGER NOT NULL,
    product_id           INTEGER NOT NULL,
    product_name         VARCHAR(255),
    price                NUMERIC(10, 2),
    quantity             INTEGER,
    total                NUMERIC(12, 2),
    discount_percentage  NUMERIC(5, 2),
    discounted_total     NUMERIC(12, 2),

    CONSTRAINT uq_cart_item_position
        UNIQUE (cart_id, item_position),

    CONSTRAINT fk_cart_items_cart
        FOREIGN KEY (cart_id) REFERENCES carts (cart_id),

    CONSTRAINT fk_cart_items_product
        FOREIGN KEY (product_id) REFERENCES products (product_id)
);
