from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from database import get_connection, init_db
from matching import rank_images_for_post
from embeddings import get_embedding

app = FastAPI(title="Image Relevance & Auto-Tagging Engine")
init_db()


class PostCreate(BaseModel):
    title: str
    body: str


class ReviewDecision(BaseModel):
    status: str


@app.get("/")
def read_root():
    return {"name": "Image Relevance Engine", "version": "1.0"}


@app.get("/images/{image_id}")
def get_image(image_id: int):
    conn = get_connection()
    image = conn.execute("SELECT * FROM images WHERE id = %s", (image_id,)).fetchone()
    conn.close()
    if image is None:
        return JSONResponse(status_code=404, content={"error": "Image not found"})
    return image


@app.post("/posts", status_code=201)
def create_post(post: PostCreate):
    if not post.title.strip() or not post.body.strip():
        return JSONResponse(status_code=400, content={"error": "Title and body are required"})

    embedding = get_embedding(f"{post.title}. {post.body}")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO posts (title, body, embedding) VALUES (%s, %s, %s) RETURNING id",
        (post.title, post.body, embedding)
    )
    new_id = cursor.fetchone()["id"]
    conn.commit()
    conn.close()

    return {"id": new_id, "title": post.title}


@app.get("/posts/{post_id}/images")
def get_ranked_images(post_id: int):
    result = rank_images_for_post(post_id)
    if "error" in result:
        return JSONResponse(status_code=404, content=result)

    conn = get_connection()
    cursor = conn.cursor()
    if result["match"]:
        cursor.execute(
            """INSERT INTO suggestions (post_id, image_id, similarity_score, guard_passed, rejection_reason)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (post_id, result["match"]["image_id"], result["match"]["similarity"], True, None)
        )
        result["suggestion_id"] = cursor.fetchone()["id"]
        conn.commit()
    conn.close()

    return result


@app.post("/suggestions/{suggestion_id}/approve")
def approve_suggestion(suggestion_id: int):
    conn = get_connection()
    conn.execute("UPDATE suggestions SET status = 'approved' WHERE id = %s", (suggestion_id,))
    conn.commit()
    conn.close()
    return {"id": suggestion_id, "status": "approved"}


@app.post("/suggestions/{suggestion_id}/reject")
def reject_suggestion(suggestion_id: int):
    conn = get_connection()
    conn.execute("UPDATE suggestions SET status = 'rejected' WHERE id = %s", (suggestion_id,))
    conn.commit()
    conn.close()
    return {"id": suggestion_id, "status": "rejected"}


@app.get("/eval/run")
def run_eval():
    conn = get_connection()
    labels = conn.execute("SELECT * FROM eval_labels").fetchall()

    if not labels:
        conn.close()
        return JSONResponse(status_code=400, content={"error": "No eval labels found — run seed_eval.py first"})

    exact_correct = 0
    category_correct = 0
    details = []

    for label in labels:
        expected_image = conn.execute("SELECT subject FROM images WHERE id = %s", (label["correct_image_id"],)).fetchone()
        expected_subject = expected_image["subject"].lower() if expected_image else ""

        result = rank_images_for_post(label["post_id"])
        top_match_id = result["match"]["image_id"] if result["match"] else None
        top_match_subject = result["match"]["subject"].lower() if result["match"] else ""

        is_exact = top_match_id == label["correct_image_id"]
        is_category_match = any(
            kw in expected_subject and kw in top_match_subject
            for kw in ["fox", "wolf", "dog", "bear", "deer"]
        )

        exact_correct += is_exact
        category_correct += is_category_match
        details.append({
            "post_id": label["post_id"],
            "expected_subject": expected_subject,
            "got_subject": top_match_subject,
            "exact_match": is_exact,
            "category_match": is_category_match,
        })

    conn.close()
    return {
        "top_1_precision_category": round(category_correct / len(labels), 3),
        "top_1_precision_exact_image": round(exact_correct / len(labels), 3),
        "total": len(labels),
        "note": "category precision = correct animal type selected; exact precision = the one literal labeled photo selected (a stricter bar when many equally-valid photos exist per category)",
        "details": details,
    }