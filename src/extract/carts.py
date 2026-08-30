import json
import requests

URL = "https://dummyjson.com/carts?limit=0"


def extract_carts():
    response = requests.get(URL)
    response.raise_for_status()

    data = response.json()
    carts = data["carts"]
    total = data["total"]

    with open("data/raw/carts.json", "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    print("Carts extracted:", len(carts))

    return carts, total