"""
Step 5: For each scene marked needs_image=True in Step 4's output, get an
image — checking the CACHE FIRST (keyed by normalized search query), and
only calling the licensed image-source APIs on a cache miss.

This is what stops "Exodus Red Sea crossing" from triggering a fresh API
call every time it recurs across your 1200 videos: the first video that
searches it pays the API call and download cost; every later video with
the same (or near-same) query reuses the stored result instantly.

Sources tried, in priority order (config.IMAGE_SOURCE_PRIORITY): Wikimedia
Commons, Met Museum, Smithsonian, Unsplash — all licensed/public-domain,
never generic web search.

Outputs:
    data/images/{image_id}.jpg               — the downloaded image file
    data/image_queries/{video_id}_assignments.json — per-scene assignment record

Usage:
    python scripts/05_fetch_images.py
    python scripts/05_fetch_images.py --video-id sermon_042
"""
import argparse
import json
import sys
import uuid
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).parent.parent))
import config
import pipeline_state as state
import cache
import image_sources


def download_image(image_url: str, image_id: str) -> str:
    """Download an image to data/images/{image_id}.jpg, return local path."""
    config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    local_path = config.IMAGES_DIR / f"{image_id}.jpg"
    resp = requests.get(image_url, timeout=config.IMAGE_DOWNLOAD_TIMEOUT_SECONDS)
    resp.raise_for_status()
    local_path.write_bytes(resp.content)
    return str(local_path)


def get_or_fetch_image(search_query: str) -> dict | None:
    """
    Cache-first image lookup. Returns the same result dict shape whether it
    came from cache or a fresh fetch:
    {image_id, source, image_url, local_path, license, title, source_page_url}
    """
    cached = cache.get_cached(search_query)
    if cached:
        return cached

    candidates = image_sources.search_all_sources_in_priority(search_query)
    if not candidates:
        return None

    best = candidates[0]  # first candidate from the highest-priority source that returned results
    image_id = uuid.uuid4().hex[:12]

    try:
        local_path = download_image(best["image_url"], image_id)
    except Exception:
        return None

    result = {
        "image_id": image_id,
        "source": best["source"],
        "image_url": best["image_url"],
        "local_path": local_path,
        "license": best.get("license"),
        "title": best.get("title"),
        "source_page_url": best.get("source_page_url"),
        "from_cache": False,
    }
    cache.set_cached(search_query, result)
    return result


def fetch_images_for_video(video_id: str) -> list:
    queries = json.loads((config.IMAGE_QUERIES_DIR / f"{video_id}_queries.json").read_text())

    assignments = []
    for q in queries:
        if not q["needs_image"] or not q["search_query"]:
            assignments.append({
                "scene_id": q["scene_id"], "start": q["start"], "end": q["end"],
                "topic": q["topic"], "image_id": None, "needs_review": False,
                "reason": "no image needed for this scene",
            })
            continue

        result = get_or_fetch_image(q["search_query"])
        if result is None:
            assignments.append({
                "scene_id": q["scene_id"], "start": q["start"], "end": q["end"],
                "topic": q["topic"], "image_id": None, "needs_review": True,
                "reason": f"no licensed image found for query: {q['search_query']}",
            })
            continue

        assignments.append({
            "scene_id": q["scene_id"], "start": q["start"], "end": q["end"],
            "topic": q["topic"],
            "image_id": result["image_id"],
            "source": result["source"],
            "license": result["license"],
            "title": result["title"],
            "local_path": result["local_path"],
            "from_cache": result["from_cache"],
            "needs_review": False,
        })
    return assignments


def main(video_id: str = None):
    state.init_db()

    queue = state.videos_ready_for("fetch_images", prior_stage="generate_image_queries")
    if video_id:
        queue = [video_id]

    if not queue:
        print("No videos ready for image fetching (need generate_image_queries = done).")
        return

    for vid in queue:
        out_path = config.IMAGE_QUERIES_DIR / f"{vid}_assignments.json"
        if out_path.exists():
            print(f"[skip] {vid} — assignments already exist")
            state.set_status(vid, "fetch_images", "done")
            continue

        print(f"[fetch_images] {vid}")
        state.set_status(vid, "fetch_images", "running")
        try:
            assignments = fetch_images_for_video(vid)
            out_path.write_text(json.dumps(assignments, ensure_ascii=False, indent=2))
            n_flagged = sum(1 for a in assignments if a["needs_review"])
            n_cached = sum(1 for a in assignments if a.get("from_cache"))
            state.set_status(
                vid, "fetch_images", "done",
                notes=f"{len(assignments)} scenes, {n_flagged} flagged, {n_cached} from cache",
            )
        except Exception as e:
            print(f"  FAILED: {e}")
            state.set_status(vid, "fetch_images", "failed", notes=str(e))

    cache.cache_stats()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id", default=None)
    args = parser.parse_args()
    main(video_id=args.video_id)
