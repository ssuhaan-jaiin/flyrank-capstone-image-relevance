from database import get_connection


def seed_eval():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as c FROM eval_labels")
    if cursor.fetchone()["c"] > 0:
        print("Eval labels already seeded, skipping.")
        conn.close()
        return

    posts = conn.execute("SELECT id, title FROM posts").fetchall()

    for post in posts:
        title_lower = post["title"].lower()
        if "fox" in title_lower:
            keyword = "fox"
        elif "wolf" in title_lower:
            keyword = "wolf"
        elif "dog" in title_lower or "puppy" in title_lower or "breed" in title_lower:
            keyword = "dog"
        elif "bear" in title_lower:
            keyword = "bear"
        elif "deer" in title_lower:
            keyword = "deer"
        else:
            continue

        image = conn.execute(
            "SELECT id FROM images WHERE subject ILIKE %s LIMIT 1", (f"%{keyword}%",)
        ).fetchone()

        if image:
            cursor.execute(
                "INSERT INTO eval_labels (post_id, correct_image_id) VALUES (%s, %s)",
                (post["id"], image["id"])
            )
            print(f"Labeled: '{post['title']}' -> image {image['id']}")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    seed_eval()