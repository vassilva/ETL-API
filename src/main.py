"""
Pipeline entry point.

    python src/main.py          extract + transform (writes data/ only)
    python src/main.py --load   extract + transform + load into PostgreSQL

Loading is opt-in so the default run never writes to the database.
"""

import argparse

from config.settings import get_settings

from extract.users import extract_users
from extract.products import extract_products
from extract.carts import extract_carts

from transform.users import transform_users
from transform.products import transform_products
from transform.carts import transform_carts

from load.users import load_users
from load.products import load_products
from load.carts import load_carts
from load.cart_items import load_cart_items


def run(load=False):
    if load:
        # Fail before calling the API if DB settings are missing
        # (only variable names are reported, never values)
        get_settings().database()

    extract_users()
    extract_products()
    extract_carts()

    transform_users()
    transform_products()
    transform_carts()

    if load:
        # Parent tables first so every foreign key already exists
        load_users()
        load_products()
        load_carts()
        load_cart_items()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run the ETL pipeline.")
    parser.add_argument(
        "--load",
        action="store_true",
        help="also load the processed data into PostgreSQL (requires DB_* settings)"
    )

    return parser.parse_args(argv)


if __name__ == "__main__":
    run(load=parse_args().load)
