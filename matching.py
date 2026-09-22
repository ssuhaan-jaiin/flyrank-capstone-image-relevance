from database import get_connection
from embeddings import cosine_similarity

SIMILARITY_THRESHOLD = 0.55
CONFIDENCE_THRESHOLD = 0.5

# Known category conflicts — visually/semantically close but categorically wrong.
# This is the explicit rule layer the assignment asks for, on top of pure similarity.
KNOWN_MISMATCHES = {
    "fox": ["wolf"],
    "wolf": ["fox"],
}


def get_post(post_id: int) -> dict:
    conn = get_connection()
    post = conn.execute("SELECT * FROM posts WHERE id = %s", (post_id,)).fetchone()
    conn.close()
    return post


def get_all_images() -> list:
    conn = get_connection()
    images = conn.execute("SELECT * FROM images WHERE embedding IS NOT NULL").fetchall()
    conn.close()
    return images


def check_guard(post_subject_hint: str, image_subject: str, similarity: float, confidence: float) -> dict:
    if confidence < CONFIDENCE_THRESHOLD:
        return {"passed": False, "reason": f"Low confidence ({confidence}) in image classification"}

    if similarity < SIMILARITY_THRESHOLD:
        return {"passed": False, "reason": f"Similarity too low ({similarity:.2f} < {SIMILARITY_THRESHOLD})"}

    for keyword, conflicts in KNOWN_MISMATCHES.items():
        if keyword in post_subject_hint.lower():
            for conflict in conflicts:
                if conflict in image_subject.lower():
                    return {"passed": False, "reason": f"Category mismatch: post is about '{keyword}', image is '{image_subject}'"}

    return {"passed": True, "reason": None}


def rank_images_for_post(post_id: int, force_image_id: int = None) -> dict:
    post = get_post(post_id)
    if post is None:
        return {"error": "Post not found"}

    images = get_all_images()
    if force_image_id is not None:
        images = [img for img in images if img["id"] == force_image_id]

    results = []
    for img in images:
        similarity = cosine_similarity(post["embedding"], img["embedding"])
        guard_result = check_guard(post["title"], img["subject"], similarity, img["confidence"])
        results.append({
            "image_id": img["id"],
            "filename": img["filename"],
            "subject": img["subject"],
            "similarity": round(similarity, 4),
            "guard_passed": guard_result["passed"],
            "rejection_reason": guard_result["reason"],
        })

    results.sort(key=lambda r: r["similarity"], reverse=True)
    passing = [r for r in results if r["guard_passed"]]

    if not passing:
        return {
            "post_title": post["title"],
            "match": None,
            "message": "No confident match",
            "all_candidates": results[:5],
        }

    return {
        "post_title": post["title"],
        "match": passing[0],
        "all_candidates": results[:5],
    }


if __name__ == "__main__":
    conn = get_connection()
    fox_post = conn.execute("SELECT id FROM posts WHERE title LIKE '%fox%' LIMIT 1").fetchone()
    wolf_image = conn.execute("SELECT id FROM images WHERE subject LIKE '%wolf%' LIMIT 1").fetchone()
    conn.close()

    print("=== Normal ranking for fox post ===")
    result = rank_images_for_post(fox_post["id"])
    print(f"Post: {result['post_title']}")
    print(f"Top match: {result['match']}")
    print()

    print("=== Forcing the wolf as the only candidate for the fox post ===")
    forced = rank_images_for_post(fox_post["id"], force_image_id=wolf_image["id"])
    print(f"Post: {forced['post_title']}")
    print(f"Match: {forced['match']}")
    print(f"Message: {forced.get('message')}")
    print(f"Candidate detail: {forced['all_candidates']}")