
"""
Step 5: For each scene marked needs_image=True in Step 4's output, get an
image — checking the CACHE FIRST (keyed by normalized search query), and
only calling the licensed image-source APIs on a cache miss.

This is what stops "Exodus Red Sea crossing" from triggering a fresh API
call every time it recurs across your 1200 videos: the first video that
searches it pays the API call and download cost; every later video with the
same (or near-same) query reuses the stored result instantly.

Sources tried, in priority order (config.IMAGE_SOURCE_PRIORITY): Wikimedia
Commons, Met Museum, Smithsonian, Unsplash — all licensed/public-domain,
never generic web search.

Outputs:
    data/images/{image_id}.jpg
    data/image_queries/{video_id}_assignments.json

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
from PIL import Image

sys.path.append(str(Path(__file__).parent.parent))

import config
import pipeline_state as state
import cache
import image_sources


def download_image(image_url: str, image_id: str) -> str:
    """Download an image to data/images/{image_id}.jpg and return local path."""

    config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    local_path = config.IMAGES_DIR / f"{image_id}.jpg"

    resp = requests.get(
        image_url,
        timeout=config.IMAGE_DOWNLOAD_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()

    local_path.write_bytes(resp.content)

    return str(local_path)


def get_image_info(image_path: str) -> dict | None:
    """
    Inspect a downloaded image.

    Returns:
        {
            "width": int,
            "height": int,
            "aspect_ratio": float
        }

    Returns None if the image is invalid/corrupt.
    """

    try:
        with Image.open(image_path) as img:
            width, height = img.size

        if width <= 0 or height <= 0:
            return None

        return {
            "width": width,
            "height": height,
            "aspect_ratio": round(width / height, 4),
        }

    except Exception:
        return None


def calculate_aspect_ratio_score(aspect_ratio: float) -> float:
    """
    Score how close an image is to the target 16:9 aspect ratio.

    This does NOT reject images simply because they are not 16:9.
    Relevance will remain more important later.

    Scores:
        100 -> very close to 16:9
         85 -> close
         65 -> acceptable
         40 -> poor
         20 -> very poor
    """

    target = config.TARGET_ASPECT_RATIO

    difference = abs(aspect_ratio - target)

    if difference <= 0.05:
        return 100.0

    if difference <= 0.15:
        return 85.0

    if difference <= 0.30:
        return 65.0

    if difference <= 0.50:
        return 40.0

    return 20.0


def calculate_image_quality_score(
    width: int,
    height: int,
    aspect_ratio: float,
) -> float:
    """
    Calculate a basic technical image-quality score.

    Currently based on:
        60% resolution
        40% aspect ratio

    This is intentionally NOT an image relevance score.
    """

    aspect_score = calculate_aspect_ratio_score(aspect_ratio)

    if width >= 1920 and height >= 1080:
        resolution_score = 100.0

    elif width >= 1280 and height >= 720:
        resolution_score = 80.0

    elif width >= 800 and height >= 600:
        resolution_score = 50.0

    else:
        resolution_score = 20.0

    score = (
        resolution_score * 0.60
        + aspect_score * 0.40
    )

    return round(score, 2)


def get_or_fetch_image(search_query: str) -> dict | None:
    """
    Cache-first image lookup.

    If an image is already cached, return it immediately.

    On cache miss:
        1. Search licensed image sources.
        2. Download candidates.
        3. Validate each candidate.
        4. Calculate technical quality.
        5. Select the best usable candidate.
        6. Cache the selected result.

    Returned result shape:

    {
        image_id,
        source,
        image_url,
        local_path,
        license,
        title,
        source_page_url,
        from_cache,
        image_width,
        image_height,
        image_aspect_ratio,
        image_quality_score,
        image_selection_method
    }
    """

    # ---------------------------------------------------------
    # CACHE FIRST
    # ---------------------------------------------------------

    cached = cache.get_cached(search_query)

    if cached:
        return cached

    # ---------------------------------------------------------
    # SEARCH LICENSED SOURCES
    # ---------------------------------------------------------

    candidates = image_sources.search_all_sources_in_priority(search_query)

    if not candidates:
        return None

    # ---------------------------------------------------------
    # EVALUATE CANDIDATES
    # ---------------------------------------------------------

    best_result = None

    for candidate in candidates:

        image_id = uuid.uuid4().hex[:12]

        try:
            local_path = download_image(
                candidate["image_url"],
                image_id,
            )

        except Exception:
            continue

        # -----------------------------------------------------
        # VALIDATE IMAGE
        # -----------------------------------------------------

        image_info = get_image_info(local_path)

        if image_info is None:

            Path(local_path).unlink(missing_ok=True)

            continue

        width = image_info["width"]
        height = image_info["height"]
        aspect_ratio = image_info["aspect_ratio"]

        # -----------------------------------------------------
        # CALCULATE QUALITY
        # -----------------------------------------------------

        quality_score = calculate_image_quality_score(
            width,
            height,
            aspect_ratio,
        )

        # -----------------------------------------------------
        # REJECT VERY SMALL / LOW QUALITY IMAGES
        # -----------------------------------------------------

        if (
            width < config.MIN_IMAGE_WIDTH
            or height < config.MIN_IMAGE_HEIGHT
            or quality_score < config.MIN_IMAGE_QUALITY_SCORE
        ):

            Path(local_path).unlink(missing_ok=True)

            continue

        # -----------------------------------------------------
        # BUILD CANDIDATE RESULT
        # -----------------------------------------------------

        candidate_result = {
            "image_id": image_id,
            "source": candidate["source"],
            "image_url": candidate["image_url"],
            "local_path": local_path,
            "license": candidate.get("license"),
            "title": candidate.get("title"),
            "source_page_url": candidate.get("source_page_url"),
            "from_cache": False,

            # Image metadata
            "image_width": width,
            "image_height": height,
            "image_aspect_ratio": aspect_ratio,
            "image_quality_score": quality_score,
            "image_selection_method": "technical_quality",
        }

        # -----------------------------------------------------
        # KEEP BEST CANDIDATE
        # -----------------------------------------------------

        if (
            best_result is None
            or quality_score > best_result["image_quality_score"]
        ):

            # Delete previously selected lower-quality image.
            if best_result is not None:
                Path(best_result["local_path"]).unlink(
                    missing_ok=True
                )

            best_result = candidate_result

        else:

            # This candidate is worse than the current best.
            Path(local_path).unlink(missing_ok=True)

    # ---------------------------------------------------------
    # NO USABLE CANDIDATE
    # ---------------------------------------------------------

    if best_result is None:
        return None

    # ---------------------------------------------------------
    # CACHE BEST RESULT
    # ---------------------------------------------------------

    cache.set_cached(
        search_query,
        best_result,
    )

    return best_result


def fetch_images_for_video(video_id: str) -> list:
    """
    Fetch and assign images for every scene in a video.
    """

    queries = json.loads(
        (
            config.IMAGE_QUERIES_DIR
            / f"{video_id}_queries.json"
        ).read_text()
    )

    assignments = []

    for q in queries:

        # -----------------------------------------------------
        # SCENE DOES NOT NEED AN IMAGE
        # -----------------------------------------------------

        if not q["needs_image"] or not q["search_query"]:

            assignments.append(
                {
                    "scene_id": q["scene_id"],
                    "start": q["start"],
                    "end": q["end"],
                    "topic": q["topic"],
                    "image_id": None,
                    "needs_review": False,
                    "reason": "no image needed for this scene",
                }
            )

            continue

        # -----------------------------------------------------
        # GET IMAGE
        # -----------------------------------------------------

        result = get_or_fetch_image(
            q["search_query"]
        )

        # -----------------------------------------------------
        # NO IMAGE FOUND
        # -----------------------------------------------------

        if result is None:

            assignments.append(
                {
                    "scene_id": q["scene_id"],
                    "start": q["start"],
                    "end": q["end"],
                    "topic": q["topic"],
                    "image_id": None,
                    "needs_review": True,
                    "reason": (
                        "no licensed image found for query: "
                        f"{q['search_query']}"
                    ),
                }
            )

            continue

        # -----------------------------------------------------
        # SUCCESSFUL IMAGE ASSIGNMENT
        # -----------------------------------------------------

        assignments.append(
            {
                "scene_id": q["scene_id"],
                "start": q["start"],
                "end": q["end"],
                "topic": q["topic"],

                "image_id": result["image_id"],
                "source": result["source"],
                "license": result["license"],
                "title": result["title"],
                "local_path": result["local_path"],

                "from_cache": result["from_cache"],

                # Image quality metadata
                "image_width": result.get("image_width"),
                "image_height": result.get("image_height"),
                "image_aspect_ratio": result.get(
                    "image_aspect_ratio"
                ),
                "image_quality_score": result.get(
                    "image_quality_score"
                ),
                "image_selection_method": result.get(
                    "image_selection_method"
                ),

                "needs_review": False,
            }
        )

    return assignments


def main(video_id: str = None):

    state.init_db()

    queue = state.videos_ready_for(
        "fetch_images",
        prior_stage="generate_image_queries",
    )

    if video_id:
        queue = [video_id]

    if not queue:

        print(
            "No videos ready for image fetching "
            "(need generate_image_queries = done)."
        )

        return

    for vid in queue:

        out_path = (
            config.IMAGE_QUERIES_DIR
            / f"{vid}_assignments.json"
        )

        # -----------------------------------------------------
        # SKIP IF ASSIGNMENTS ALREADY EXIST
        # -----------------------------------------------------

        if out_path.exists():

            print(
                f"[skip] {vid} — assignments already exist"
            )

            state.set_status(
                vid,
                "fetch_images",
                "done",
            )

            continue

        print(f"[fetch_images] {vid}")

        state.set_status(
            vid,
            "fetch_images",
            "running",
        )

        try:

            assignments = fetch_images_for_video(
                vid
            )

            out_path.write_text(
                json.dumps(
                    assignments,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            n_flagged = sum(
                1
                for a in assignments
                if a["needs_review"]
            )

            n_cached = sum(
                1
                for a in assignments
                if a.get("from_cache")
            )

            state.set_status(
                vid,
                "fetch_images",
                "done",
                notes=(
                    f"{len(assignments)} scenes, "
                    f"{n_flagged} flagged, "
                    f"{n_cached} from cache"
                ),
            )

        except Exception as e:

            print(
                f"  FAILED: {e}"
            )

            state.set_status(
                vid,
                "fetch_images",
                "failed",
                notes=str(e),
            )

    cache.cache_stats()


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--video-id",
        default=None,
    )

    args = parser.parse_args()

    main(
        video_id=args.video_id
    )

