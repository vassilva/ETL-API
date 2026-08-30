from extract.users import extract_users
from extract.products import extract_products
from extract.carts import extract_carts

from transform.users import transform_users
from transform.products import transform_products
from transform.carts import transform_carts


def run():
    extract_users()
    extract_products()
    extract_carts()

    transform_users()
    transform_products()
    transform_carts()


if __name__ == "__main__":
    run()