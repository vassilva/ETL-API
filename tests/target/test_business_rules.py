"""
Target business rules, evaluated set-based inside PostgreSQL.

Each rule is a query returning one row per violating record; the test
reports the violation count and sample business keys. Rules are recomputed
from the stored values independently of the transform code.

The rules the ETL itself implements (derived columns) are smoke, the PR
critical path; the others run in the pre-merge regression.
"""

import pytest

from support.db_helpers import violations


pytestmark = [pytest.mark.load, pytest.mark.database]


CI_KEY = "ci.cart_id::text || ':' || ci.item_position::text"

# (rule id, sample key expression, FROM/WHERE returning violating rows)
BUSINESS_RULES = [
    ("users.full_name = first_name + ' ' + last_name", "u.user_id",
     "FROM users u WHERE u.full_name IS DISTINCT FROM u.first_name || ' ' || u.last_name"),
    ("users.email has a valid format", "u.user_id",
     r"FROM users u WHERE u.email !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'"),
    ("products.product_name ends with exactly one ' - RP'", "p.product_id",
     r"FROM products p WHERE p.product_name !~ '\S - RP$' OR p.product_name LIKE '% - RP - RP'"),
    ("products.price > 0", "p.product_id",
     "FROM products p WHERE p.price <= 0"),
    ("products.discount_percentage between 0 and 100", "p.product_id",
     "FROM products p WHERE p.discount_percentage NOT BETWEEN 0 AND 100"),
    ("products.rating between 0 and 5", "p.product_id",
     "FROM products p WHERE p.rating NOT BETWEEN 0 AND 5"),
    ("products.stock >= 0", "p.product_id",
     "FROM products p WHERE p.stock < 0"),
    ("products.discounted_price = ROUND(price * (1 - discount / 100), 2)", "p.product_id",
     "FROM products p WHERE p.discounted_price IS DISTINCT FROM "
     "ROUND(p.price * (1 - p.discount_percentage / 100), 2)"),
    ("carts.discounted_total <= total", "c.cart_id",
     "FROM carts c WHERE c.discounted_total > c.total"),
    ("carts have at least one item", "c.cart_id",
     "FROM carts c WHERE NOT EXISTS (SELECT 1 FROM cart_items ci WHERE ci.cart_id = c.cart_id)"),
    # LEFT JOIN: a cart that lost all its items is compared against zero
    # instead of silently disappearing from the check
    ("carts totals = aggregate of their items", "c.cart_id",
     """
     FROM carts c
     LEFT JOIN (
         SELECT cart_id,
                SUM(total) AS total,
                SUM(discounted_total) AS discounted_total,
                SUM(quantity) AS quantity,
                COUNT(*) AS items
         FROM cart_items
         GROUP BY cart_id
     ) i ON i.cart_id = c.cart_id
     WHERE c.total IS DISTINCT FROM COALESCE(i.total, 0)
        OR c.discounted_total IS DISTINCT FROM COALESCE(i.discounted_total, 0)
        OR c.total_quantity IS DISTINCT FROM COALESCE(i.quantity, 0)
        OR c.total_products IS DISTINCT FROM COALESCE(i.items, 0)
     """),
    ("cart_items.quantity > 0", CI_KEY,
     "FROM cart_items ci WHERE ci.quantity <= 0"),
    ("cart_items.total = ROUND(price * quantity, 2)", CI_KEY,
     "FROM cart_items ci WHERE ci.total IS DISTINCT FROM ROUND(ci.price * ci.quantity, 2)"),
    ("cart_items.discounted_total <= total", CI_KEY,
     "FROM cart_items ci WHERE ci.discounted_total > ci.total"),
    ("cart_items.item_position is 1..n per cart", "g.cart_id",
     """
     FROM (
         SELECT cart_id
         FROM cart_items
         GROUP BY cart_id
         HAVING MIN(item_position) <> 1 OR MAX(item_position) <> COUNT(*)
     ) g
     """),
]


# Derived columns computed by the transform: smoke (PR critical path)
SMOKE_RULES = {
    "users.full_name = first_name + ' ' + last_name",
    "products.product_name ends with exactly one ' - RP'",
    "products.discounted_price = ROUND(price * (1 - discount / 100), 2)",
}

# A renamed rule must never silently drop out of smoke
assert SMOKE_RULES <= {r[0] for r in BUSINESS_RULES}, "SMOKE_RULES names an unknown rule"


# Validate each business rule over the complete target table
@pytest.mark.parametrize(
    "rule_id, key_sql, from_sql",
    [
        pytest.param(*rule, id=rule[0], marks=[pytest.mark.smoke] if rule[0] in SMOKE_RULES else [])
        for rule in BUSINESS_RULES
    ]
)
def test_business_rule(db_connection, rule_id, key_sql, from_sql):
    count, keys = violations(db_connection, key_sql, from_sql)

    assert count == 0, f"[Database] rule: {rule_id} | violations: {count} | sample keys: {keys}"
