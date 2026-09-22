import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]


def get_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id SERIAL PRIMARY KEY,
            filename TEXT NOT NULL,
            subject TEXT,
            category TEXT,
            attributes JSONB,
            caption TEXT,
            confidence FLOAT,
            embedding FLOAT8[],
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            embedding FLOAT8[],
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suggestions (
            id SERIAL PRIMARY KEY,
            post_id INTEGER REFERENCES posts(id),
            image_id INTEGER REFERENCES images(id),
            similarity_score FLOAT,
            guard_passed BOOLEAN,
            rejection_reason TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eval_labels (
            id SERIAL PRIMARY KEY,
            post_id INTEGER REFERENCES posts(id),
            correct_image_id INTEGER REFERENCES images(id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_category ON images(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_suggestions_post ON suggestions(post_id)")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized.")