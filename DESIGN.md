# Design — Image Relevance & Auto-Tagging Engine

## Problem

A blog has a library of images and a stream of posts. Each post needs the right image — the one whose subject actually matches the post's topic. Picking wrong (a wolf photo on a fox article) is worse than picking nothing. The system must recommend confidently when it's right, and say "no confident match" when it isn't.

## Non-goal

This system does not generate images. It only understands, tags, and matches an existing library — image generation is explicitly out of scope.

## Data model

- **images** — one row per image: extracted `subject`, `category`, `attributes` (JSONB), `caption`, `confidence` (from the vision model), and `embedding` (float array, from the caption).
- **posts** — one row per blog post: `title`, `body`, `embedding` (from title + body).
- **suggestions** — one row per (post, image) pairing evaluated: `similarity_score`, `guard_passed`, `rejection_reason`, and a review `status` (pending/approved/rejected).
- **eval_labels** — the hand-labeled ground truth: for a given post, which image is actually correct. Used to compute top-1 precision.

## API surface (sketch, refined in later phases)

- `POST /images/ingest` — trigger the batch vision-tagging job over the corpus
- `GET /images/{id}` — one image's extracted metadata
- `POST /posts` — create a post (triggers embedding)
- `GET /posts/{id}/images` — ranked, guard-checked suggestions for a post
- `POST /suggestions/{id}/approve` / `/reject` — review workflow
- `GET /eval/run` — compute and return top-1 precision against `eval_labels`

## Matching strategy

1. **Vision tagging** — each image goes through Gemini Flash, producing `{subject, category, attributes, caption, confidence}`, validated against a Pydantic schema. Invalid or malformed responses are retried once, then flagged, never silently accepted.
2. **Embedding** — each image's caption and each post's title+body are embedded into the same vector space (Gemini embeddings).
3. **Ranking** — for a given post, every image is scored by cosine similarity between the post's embedding and the image's caption embedding.
4. **Mismatch guard** — before a top-ranked candidate is returned as a suggestion, it must clear three checks:
   - `similarity_score >= SIMILARITY_THRESHOLD` (starting value: 0.75, tuned in Phase 3 against the labeled eval set)
   - `confidence >= CONFIDENCE_THRESHOLD` (starting value: 0.5)
   - the image's `category` is not a known mismatch for the post's inferred subject (e.g. "wolf" categorically rejected for a post about "fox")
   - If no candidate clears all three, the endpoint returns "no confident match" with the specific reason(s) it failed.

## Dataset

50 images across 5 categories (red fox, wolf, dog, bear, deer), sourced from Pexels (free, licensed). The fox/wolf pair is deliberately close visually — this is the exact pairing used to prove the guard actually discriminates, not just ranks.