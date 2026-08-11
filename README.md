# Biblical Theology Video Captioning & Image Pipeline

Implements the finalized 6-step architecture: extract audio → transcribe →
segment into scenes → generate image search queries → fetch images from
licensed sources (cached) → compile a clean handoff sheet for the video
editing team. Rendering itself is out of scope — this pipeline hands off
structured data + downloaded images + transcript, nothing more.

## Pipeline steps

| Step | Script | Input | Output |
|---|---|---|---|
| 1. Extract audio | `scripts/01_extract_audio.py` | `data/raw_videos/{video_id}.mp4` | `data/raw_audio/{video_id}.wav` |
| 2. Transcribe | `scripts/02_transcribe.py` | audio | `data/transcripts/{video_id}_words.json` (word-level timestamps) |
| 3. Segment into scenes | `scripts/03_segment_transcript.py` | transcript | `data/scene_manifests/{video_id}_scenes.json` (each scene has a unique `scene_id`) |
| 4. Generate image queries | `scripts/04_generate_image_queries.py` | scene manifest | `data/image_queries/{video_id}_queries.json` (needs_image + search_query per scene) |
| 5. Fetch images (cached) | `scripts/05_fetch_images.py` | queries | `data/images/{image_id}.jpg` + `data/image_queries/{video_id}_assignments.json` |
| 6. Generate handoff sheet | `scripts/06_generate_handoff_sheet.py` | assignments + transcript | `data/handoff/{video_id}_handoff.csv` |

Every video's progress through these 6 stages is tracked in
`pipeline_state.db` (SQLite) — resumable, auditable, query anytime with
`scripts/check_status.py`.

## The image query cache — how it saves you API calls

`cache.py` stores every image search result keyed by a NORMALIZED version
of the search query, in the `image_query_cache` table inside
`pipeline_state.db`. The first time any scene, in any video, searches for
e.g. "Exodus Red Sea crossing," Step 5:

1. Checks the cache — miss.
2. Calls the licensed image sources in priority order until one returns a result.
3. Downloads the image, assigns it a unique `image_id`.
4. Stores the result in the cache under the normalized query.

Every later scene — in this video or any other — that searches a matching
query gets the cached result instantly: no API call, no download, no
rate-limit consumption. Given a biblical theology course repeats major
narrative beats (creation, flood, Exodus, exile, crucifixion, etc.) across
many videos, this should cut your real API call volume well below the
raw "1200 videos × ~25 scenes" estimate.

Query normalization (lowercase, strip punctuation, sort words) catches
exact and near-exact repeats. If you find topically-identical scenes
phrased too differently to collapse to the same cache key, that's a sign
to upgrade `normalize_query()` to an embedding-similarity match instead of
exact string matching — noted as a comment in `cache.py`.

## Image sources — licensed only, no copyright risk

`image_sources.py` only queries sources with clear public-domain/CC0/free
licensing:

- **Wikimedia Commons** — no API key needed
- **Met Museum Open Access** — no API key needed, all CC0
- **Smithsonian Open Access** — needs a free api.data.gov key, all CC0
- **Unsplash** — needs a free API key, for landscape/geographic backdrop photos

Priority order is set in `config.IMAGE_SOURCE_PRIORITY`. Generic web/Google
Image search is deliberately NOT included — those results carry no clear
usage rights for embedding in 1200 published videos.

## Setup

```bash
cd biblical_video_pipeline
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# ffmpeg must be installed separately (system package, not pip)
# Ubuntu: sudo apt install ffmpeg

cp .env.example .env
# then fill in ANTHROPIC_API_KEY (required)
# UNSPLASH_ACCESS_KEY / SMITHSONIAN_API_KEY are optional — only needed if
# you keep those sources enabled in config.IMAGE_SOURCE_PRIORITY
```

## Recommended build order (pilot before scaling to 1200)

1. Drop 3-5 representative videos into `data/raw_videos/` as `.mp4` files
   named by whatever you want as their `video_id` (e.g. `sermon_001.mp4`).
2. Run Steps 1 → 2. Spot-check a transcript JSON against the actual video
   for timestamp accuracy.
3. Run Step 3. Read the scene manifests by hand — this is still the most
   important file in the pipeline to get right.
4. Run Step 4. Check that `needs_image` decisions and search queries make
   sense — are the queries concrete enough to actually find something?
5. Run Step 5. Check `data/images/` — did it find reasonable images? Check
   `_assignments.json` for `needs_review` flags. Run `scripts/check_status.py`
   to see cache hit stats.
6. Run Step 6. Open the resulting CSV in Excel/Sheets — is this something
   you'd hand to an editor?
7. Only once all of this looks right on the pilot batch, run the same
   scripts with no `--video-id` argument to process everything currently
   in `data/raw_videos/`.

## Running a stage across all videos

```bash
python scripts/01_extract_audio.py
python scripts/02_transcribe.py
python scripts/03_segment_transcript.py
python scripts/04_generate_image_queries.py
python scripts/05_fetch_images.py
python scripts/06_generate_handoff_sheet.py
python scripts/check_status.py     # check progress / cache stats any time
```

Each script skips videos already completed and only processes what's
`pending` at that stage — safe to re-run after a failure or interruption.

## Human review

Any row in a handoff CSV with `needs_review = True` (no licensed image
found, or the video hasn't cleared QA) should be checked by a person
before the video goes to editing. This scaffold doesn't include a review
UI yet — worth adding once your pilot is validated.

## Not yet in scope, deliberately

- **Rendering** (burning images/captions into the actual video) — the
  editing team's job.
- **Parallel/concurrent processing across multiple videos** — the scripts
  run sequentially by design, matching a validate-first approach. Once the
  pilot is solid, wrapping these stages in a workflow orchestrator (e.g.
  Prefect) with a concurrency limit is the natural next step — ask when
  you're ready to build that.
