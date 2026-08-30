import json
import requests

URL = "https://dummyjson.com/products?limit=0"


def extract_products():
    response = requests.get(URL)
    response.raise_for_status()

    data = response.json()
    products = data["products"]
    total = data["total"]

    with open("data/raw/products.json", "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    print("Products extracted:", len(products))

    return products, total