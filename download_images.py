import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
IMAGES_DIR = Path("images")
IMAGES_DIR.mkdir(exist_ok=True)

CATEGORIES = {
    "red_fox": "red fox",
    "wolf": "gray wolf",
    "dog": "dog",
    "bear": "brown bear",
    "deer": "deer",
}
PER_CATEGORY = 10


def download_category(category_key, query):
    headers = {"Authorization": PEXELS_API_KEY}
    response = requests.get(
        "https://api.pexels.com/v1/search",
        headers=headers,
        params={"query": query, "per_page": PER_CATEGORY}
    )
    response.raise_for_status()
    data = response.json()

    for i, photo in enumerate(data["photos"]):
        img_url = photo["src"]["medium"]
        img_response = requests.get(img_url)
        filename = IMAGES_DIR / f"{category_key}_{i+1}.jpg"
        filename.write_bytes(img_response.content)
        print(f"Saved {filename}")


if __name__ == "__main__":
    for key, query in CATEGORIES.items():
        download_category(key, query)