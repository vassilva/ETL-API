import json
import requests

URL = "https://dummyjson.com/users?limit=0"


def extract_users():
    response = requests.get(URL)
    response.raise_for_status()

    data = response.json()
    users = data["users"]
    total = data["total"]

    with open("data/raw/users.json", "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    print("Users extracted:", len(users))

    return users, total