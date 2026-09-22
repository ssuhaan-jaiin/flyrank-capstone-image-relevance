from database import get_connection
from embeddings import get_embedding
import json

POSTS = [
    ("The secret life of red foxes", "Red foxes are highly adaptable animals found across forests, grasslands, and even cities. Their thick orange coats and bushy tails make them one of the most recognizable wild animals."),
    ("Why foxes thrive in urban areas", "Urban red foxes have learned to scavenge in cities worldwide, showing remarkable intelligence and adaptability to human environments."),
    ("Understanding wolf pack behavior", "Grey wolves live and hunt in tightly organized packs, with complex social hierarchies led by a breeding pair. Their howls can travel for miles."),
    ("The return of wolves to Yellowstone", "Wolf reintroduction to Yellowstone National Park in the 1990s dramatically reshaped the ecosystem, a phenomenon known as trophic cascade."),
    ("Choosing the right dog breed for your family", "Different dog breeds suit different lifestyles. Active families often do well with energetic breeds, while apartment dwellers may prefer calmer companions."),
    ("Training tips for a new puppy", "Consistency and positive reinforcement are the foundation of good puppy training. Start with basic commands and short daily sessions."),
    ("Brown bears preparing for hibernation", "Before winter, brown bears enter a period of intense eating called hyperphagia, gaining significant weight to survive months without food."),
    ("Bear safety tips for hikers", "When hiking in bear country, make noise, carry bear spray, and store food properly to avoid unwanted encounters with brown bears."),
    ("The graceful movement of deer in the wild", "Deer are known for their alert nature and remarkable agility, able to leap significant heights and distances to escape predators."),
    ("Deer populations and forest ecosystems", "Deer play a major role in shaping forest undergrowth through their grazing habits, influencing which plant species thrive."),
]


def seed():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as c FROM posts")
    if cursor.fetchone()["c"] > 0:
        print("Posts already seeded, skipping.")
        conn.close()
        return

    for title, body in POSTS:
        print(f"Embedding post: {title}")
        embedding = get_embedding(f"{title}. {body}")
        cursor.execute(
            "INSERT INTO posts (title, body, embedding) VALUES (%s, %s, %s)",
            (title, body, embedding)
        )

    conn.commit()
    conn.close()
    print(f"Seeded {len(POSTS)} posts.")


def embed_images():
    conn = get_connection()
    cursor = conn.cursor()

    rows = conn.execute("SELECT id, filename, caption FROM images WHERE embedding IS NULL").fetchall()
    print(f"Embedding {len(rows)} images (skipping already-embedded)...")

    for row in rows:
        embedding = get_embedding(row["caption"])
        cursor.execute("UPDATE images SET embedding = %s WHERE id = %s", (embedding, row["id"]))
        conn.commit()

    conn.close()
    print("Done embedding images.")


if __name__ == "__main__":
    seed()
    embed_images()