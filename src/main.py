"""
Pipeline entry point.

    python src/main.py                     extract + transform (writes data/ only)
    python src/main.py --load              extract + transform + load into PostgreSQL
    python src/main.py --stage <name>      one stage only: extract, transform or load

Loading is opt-in so the default run never writes to the database. Running
one stage at a time lets CI report Extract, Transform and Load separately;
each stage reads the files the previous one wrote to data/.
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


def run_extract():
    extract_users()
    extract_products()
    extract_carts()


def run_transform():
    transform_users()
    transform_products()
    transform_carts()


def run_load():
    # Parent tables first so every foreign key already exists
    load_users()
    load_products()
    load_carts()
    load_cart_items()


STAGES = {
    "extract": run_extract,
    "transform": run_transform,
    "load": run_load,
}


def check_database_settings():
    # Fail before any work if DB settings are missing
    # (only variable names are reported, never values)
    get_settings().database()


def run(load=False):
    if load:
        check_database_settings()

    run_extract()
    run_transform()

    if load:
        run_load()


def run_stage(name):
    if name == "load":
        check_database_settings()

    STAGES[name]()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run the ETL pipeline.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--load",
        action="store_true",
        help="also load the processed data into PostgreSQL (requires DB_* settings)"
    )
    mode.add_argument(
        "--stage",
        choices=STAGES,
        help="run a single stage (load requires DB_* settings)"
    )

    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()

    if args.stage:
        run_stage(args.stage)
    else:
        run(load=args.load)
