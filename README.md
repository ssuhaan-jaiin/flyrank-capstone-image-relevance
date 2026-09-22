# Image Relevance & Auto-Tagging Engine

FlyRank Internship capstone — Backend AI Engineering track. A system that understands an image library, tags it automatically via a local vision model, and matches the right image to the right blog post — with a mismatch guard that refuses low-confidence or category-wrong suggestions instead of guessing.

## Architecture

```
Images --(batch job, local vision model)--> {subject, category, attributes, caption, confidence}
  |                                                    |
  |                                          embed(caption) --> image embeddings
  |
Posts --> embed(title + body) --> post embeddings
  |
GET /posts/:id/images
  --> cosine similarity ranking (post embedding x image embeddings)
  --> Mismatch Guard:
        - confidence >= 0.5 ?
        - similarity >= 0.55 ?
        - known category conflict (e.g. fox <-> wolf)?
  --> passing match, ranked highest similarity first
  --> OR "no confident match" + reason, if nothing clears the bar
  --> Review API: approve / reject
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in DATABASE_URL, PEXELS_API_KEY (Gemini key optional, unused in final pipeline)

docker run --name imgdb -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=imagerelevance \
  -p 5432:5432 -v imgdata:/var/lib/postgresql -d postgres

ollama pull gemma3:4b
ollama pull nomic-embed-text
ollama serve &

python3 database.py
python3 download_images.py     # pulls 50 images across 5 categories from Pexels
python3 vision.py              # tags all 50 images with the local vision model
python3 seed_posts.py          # seeds 10 sample posts + embeds all images
python3 seed_eval.py           # builds the labeled evaluation set

uvicorn main:app --reload
```

API runs at `http://localhost:8000`.

## Dataset

50 images across 5 categories (red fox, grey wolf, dog, brown bear, deer), sourced from Pexels — deliberately chosen because fox/wolf are visually and semantically close, making them a real test of the mismatch guard rather than an easy case.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | / | API info |
| GET | /images/{id} | One image's tagged metadata |
| POST | /posts | Create a post (auto-embedded) |
| GET | /posts/{id}/images | Ranked, guard-checked suggestions for a post |
| POST | /suggestions/{id}/approve | Approve a suggestion |
| POST | /suggestions/{id}/reject | Reject a suggestion |
| GET | /eval/run | Run the labeled evaluation, report precision |

## The mismatch guard

Three independent checks must all pass before a suggestion is accepted:
1. **Confidence** — the vision model's own classification confidence must be >= 0.5
2. **Similarity** — cosine similarity between post and image embeddings must be >= 0.55
3. **Category conflict** — an explicit rule table catches known visually-similar-but-wrong pairs (fox/wolf) even when similarity alone would pass

**Proof this matters, not just exists:** forcing a grey wolf image as the only candidate for a red fox post produced similarity `0.589` — *above* the 0.55 threshold, meaning pure similarity would have accepted it. The category rule caught it anyway: `"Category mismatch: post is about 'fox', image is 'grey wolf'"`. Rejected, with a human-readable reason. See `EVIDENCE.md` for the full transcript.

## Evaluation

9 labeled posts, each matched to the correct animal category.

- **Top-1 category precision: 1.0** (9/9) — the system selected the correct *animal type* for every post.
- **Top-1 exact-image precision: 0.0** — the system rarely picked the one arbitrary photo hand-labeled as "the" answer, because 10 equally-valid photos exist per category and it reasonably picked a different (but equally correct) one each time. Category precision is the meaningful number here; exact-image precision is reported for transparency but isn't the right bar for a corpus with multiple correct answers per class.

## AI processing details

- **Vision model:** local, via Ollama (`gemma3:4b`) — chosen after `moondream` repeatedly produced bounding-box coordinates instead of the requested JSON schema (a training mismatch, not a prompt issue). See `BUILDLOG.md` for the full debugging trail.
- **Embeddings:** local, via Ollama (`nomic-embed-text`).
- **Cost:** $0 — fully local pipeline. `output/cost_log.json` logs every vision call made, including the Gemini calls made before switching to local (all at $0, free tier).
- **Structured output validation:** every vision response is validated against a Pydantic schema before storage; malformed responses are retried (up to 3 attempts) and logged as failures if still invalid, never silently accepted.

## Known limitations

- Vision model confidence scores skew high and uniform (0.85–0.98 range) — `gemma3:4b` doesn't calibrate confidence as distinctly as a larger model might, so the low-confidence flag never triggered on this corpus. The threshold logic is present and tested via code, just not exercised by this particular dataset.
- The category-conflict rule table (`KNOWN_MISMATCHES`) is hand-curated for the fox/wolf pair specifically — a production version would need a broader or learned conflict-detection approach for arbitrary categories.
- No browser or UI beyond the raw API — review workflow is endpoints + a database table, per the capstone's own stated scope.