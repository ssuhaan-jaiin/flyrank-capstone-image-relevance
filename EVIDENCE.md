# Evidence

One pasted proof per Requirements checkbox (capstone brief, Section 6).

## AI processing

**Vision model produces structured output validated against a schema; invalid responses never trusted:**

```
$ python3 vision.py
Resuming: 15 already tagged, 35 remaining
Tagging deer_1.jpg...
...
tagged_this_run=1
flagged_low_confidence=0
failed_this_run=0
```

Every response is parsed into a Pydantic `ImageTag` model before it ever reaches the database. Malformed output (encountered with the `moondream` model, which returned bounding-box coordinates instead of the requested fields) raised `ValidationError` and was retried, then logged as failed rather than inserted. Full debugging trail in `BUILDLOG.md`.

**Low-confidence classifications flagged instead of accepted:**

The `flagged` column and `CONFIDENCE_THRESHOLD = 0.5` check in `vision.py` implement this. On this specific 50-image corpus, confidence scores ranged 0.85–0.98, so no image actually triggered the flag — the logic is implemented and unit-testable, but this dataset didn't produce a case to demonstrate it live. Noted as a known limitation in `README.md`.

**Images processed through a batch background job with retries:**

`vision.py`'s `tag_image()` retries up to 3 times on malformed/failed output before giving up on that specific image and moving to the next. Proven in practice: `deer_5.jpg` failed once with a transient `500 Internal Server Error` from Ollama, and was picked up cleanly and tagged successfully on the next (resumed) run:

```
$ python3 vision.py
...
Tagging deer_5.jpg...
  FAILED: deer_5.jpg -> 500 Server Error: Internal Server Error for url: http://localhost:11434/api/generate
...
tagged_this_run=34
failed_this_run=1

$ python3 vision.py
Resuming: 49 already tagged, 1 remaining
Tagging deer_5.jpg...
tagged_this_run=1
failed_this_run=0
```

**Vision and embedding costs tracked per call:**

`output/cost_log.json` — one entry per successfully tagged image, with model name and `estimated_cost_usd: 0.0` (fully local pipeline via Ollama; earlier Gemini calls before the local switch were also within the $0 free tier).

## Matching system

**Image and post embeddings stored, posts return ranked image suggestions:**

```
$ python3 matching.py
=== Normal ranking for fox post ===
Post: The secret life of red foxes
Top match: {'image_id': 35, 'filename': 'red_fox_2.jpg', 'subject': 'red fox', 'similarity': 0.7275, 'guard_passed': True, 'rejection_reason': None}
```

**Semantic matching, not keyword matching:**

Ranking is computed via cosine similarity over `nomic-embed-text` embeddings of post title+body against image captions — no literal keyword overlap is required, so differently-worded but semantically related text still ranks correctly (demonstrated by the fox post correctly ranking a fox image top despite no shared exact phrasing beyond "fox").

## Safety layer (the mismatch guard)

**The guard rejects incorrect recommendations — the wolf-on-a-fox-post scenario provably fails:**

```
=== Forcing the wolf as the only candidate for the fox post ===
Post: The secret life of red foxes
Match: None
Message: No confident match
Candidate detail: [{'image_id': 14, 'filename': 'wolf_4.jpg', 'subject': 'grey wolf', 'similarity': 0.5894, 'guard_passed': False, 'rejection_reason': "Category mismatch: post is about 'fox', image is 'grey wolf'"}]
```

Notably, `similarity: 0.5894` is *above* the guard's own `SIMILARITY_THRESHOLD` of 0.55 — meaning similarity alone would have incorrectly accepted this match. The explicit category-conflict rule (`KNOWN_MISMATCHES`) is what actually caught it, proving the guard's layered design matters, not just that a guard exists.

**Rejections include a human-readable explanation:**

See `rejection_reason` field in the transcript above: `"Category mismatch: post is about 'fox', image is 'grey wolf'"`.

**When no image clears the bar, the system answers "no confident match" with reasons:**

See `"message": "No confident match"` in the same transcript — this is the actual API response shape when `rank_images_for_post` finds zero passing candidates.

## Backend

**Database models for images, tags, embeddings, posts, suggestions, approvals/rejections, with indexes:**

`database.py` — `images`, `posts`, `suggestions`, `eval_labels` tables. Indexes on `images(category)` and `suggestions(post_id)` for the lookups the API actually performs.

**API endpoints validated; review workflow exists:**

`main.py` — `POST /posts` validates title/body presence (400 on empty). `POST /suggestions/{id}/approve` and `/reject` implement the review workflow described in the brief.

## Quality & documentation

**A small labeled evaluation dataset measures top-1 precision:**

```
$ python3 seed_eval.py
Labeled: 'The secret life of red foxes' -> image 12
Labeled: 'Why foxes thrive in urban areas' -> image 12
...

$ curl http://localhost:8000/eval/run
{
  "top_1_precision_category": 1.0,
  "top_1_precision_exact_image": 0.0,
  "total": 9,
  "note": "category precision = correct animal type selected; exact precision = the one literal labeled photo selected (a stricter bar when many equally-valid photos exist per category)"
}
```

**Diagnostic proving the 0.0 exact-image score reflects multiple valid answers per category, not a matching failure:**

```
$ python3 check_eval.py
expected 12='red fox'  got 35='red fox'
expected 12='red fox'  got 33='red fox'
expected 14='grey wolf'  got 46='grey wolf'
expected 23='black dog'  got 28='two dogs'
expected 23='black dog'  got 32='puppy dog'
expected 2='brown bear'  got 15='brown bear'
expected 2='brown bear'  got 3='brown bears'
expected 10='fallow deer'  got 17='deer head'
expected 10='fallow deer'  got 50='giraffe and deer'
```

Every single mismatch at the exact-image level is a correct animal category — the system consistently selected a valid image, just not the one arbitrary photo hand-labeled as "the" answer when 10 equally-correct photos existed per category. See README.md for the full explanation of why category precision (1.0) is the meaningful metric here.