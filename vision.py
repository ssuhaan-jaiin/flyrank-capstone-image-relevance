import os
import json
import base64
import time
import requests
from pathlib import Path
from pydantic import BaseModel, ValidationError
from typing import List
from database import get_connection

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"
CONFIDENCE_THRESHOLD = 0.5
MAX_ATTEMPTS = 3


class ImageTag(BaseModel):
    subject: str
    category: str
    attributes: List[str]
    caption: str
    confidence: float


PROMPT = """Look at this image and respond with ONLY a JSON object (no markdown, no explanation) with exactly these fields:
{
  "subject": "the main subject, 1-3 words, e.g. 'red fox'",
  "category": "general category, one word, e.g. 'animal'",
  "attributes": ["3-5 short descriptive attributes"],
  "caption": "one sentence describing the image",
  "confidence": 0.0 to 1.0, how confident you are in this classification
}"""


def tag_image(image_path: Path) -> dict:
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": PROMPT,
                    "images": [image_b64],
                    "format": "json",
                    "stream": False,
                },
                timeout=60,
            )
            response.raise_for_status()
            raw_text = response.json()["response"]
            data = json.loads(raw_text)
            tag = ImageTag(**data)
            return {"tag": tag, "flagged": tag.confidence < CONFIDENCE_THRESHOLD}
        except (json.JSONDecodeError, ValidationError, KeyError) as e:
            print(f"  attempt {attempt} malformed output: {e}")
            if attempt == MAX_ATTEMPTS:
                raise
            time.sleep(1)


def get_tagged_filenames():
    conn = get_connection()
    rows = conn.execute("SELECT filename FROM images").fetchall()
    conn.close()
    return {r["filename"] for r in rows}


def run_batch():
    already_tagged = get_tagged_filenames()
    image_files = [f for f in sorted(Path("images").glob("*.jpg")) if f.name not in already_tagged]
    print(f"Resuming: {len(already_tagged)} already tagged, {len(image_files)} remaining")

    conn = get_connection()
    cursor = conn.cursor()

    cost_entries = []
    tagged = 0
    flagged_count = 0
    failed = []

    for image_path in image_files:
        print(f"Tagging {image_path.name}...")
        try:
            result = tag_image(image_path)
        except Exception as e:
            print(f"  FAILED: {image_path.name} -> {e}")
            failed.append({"file": image_path.name, "reason": str(e)})
            continue

        tag = result["tag"]
        cursor.execute(
            """INSERT INTO images (filename, subject, category, attributes, caption, confidence, flagged)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (image_path.name, tag.subject, tag.category, json.dumps(tag.attributes),
             tag.caption, tag.confidence, result["flagged"])
        )
        conn.commit()
        tagged += 1

        if result["flagged"]:
            flagged_count += 1
            print(f"  FLAGGED (low confidence: {tag.confidence})")

        cost_entries.append({"file": image_path.name, "model": "local:moondream", "estimated_cost_usd": 0.0})

    conn.close()

    Path("output").mkdir(exist_ok=True)
    cost_log_path = Path("output/cost_log.json")
    existing = json.loads(cost_log_path.read_text()) if cost_log_path.exists() else []
    cost_log_path.write_text(json.dumps(existing + cost_entries, indent=2))

    print(f"tagged_this_run={tagged}")
    print(f"flagged_low_confidence={flagged_count}")
    print(f"failed_this_run={len(failed)}")


if __name__ == "__main__":
    run_batch()