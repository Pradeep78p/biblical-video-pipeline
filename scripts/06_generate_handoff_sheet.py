"""
Step 6: Compile everything into one clean CSV per video.

Includes:
    - video ID
    - scene timestamps
    - topic
    - assigned image
    - image source/license
    - local image path
    - image dimensions
    - image aspect ratio
    - image quality score
    - validation status
    - review status
    - transcript text

Outputs:
    data/handoff/{video_id}_handoff.csv
    data/handoff/all_videos_summary.csv

Usage:
    python scripts/06_generate_handoff_sheet.py
    python scripts/06_generate_handoff_sheet.py --video-id sermon_042
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import config
import pipeline_state as state


def scene_transcript_text(words: list, start: float, end: float) -> str:
    """
    Extract transcript words belonging to a scene.
    """

    return " ".join(
        w["word"].strip()
        for w in words
        if start <= w["start"] < end
    )


def generate_handoff_for_video(video_id: str):
    """
    Generate one handoff CSV for a video.
    """

    assignments_path = (
        config.IMAGE_QUERIES_DIR
        / f"{video_id}_assignments.json"
    )

    if not assignments_path.exists():
        raise FileNotFoundError(
            f"Assignment file not found: {assignments_path}"
        )

    assignments = json.loads(
        assignments_path.read_text()
    )

    # ---------------------------------------------------------
    # Load transcript words if enabled
    # ---------------------------------------------------------

    words = []

    if config.HANDOFF_INCLUDE_SCENE_TRANSCRIPT_TEXT:

        transcript_path = (
            config.TRANSCRIPTS_DIR
            / f"{video_id}_words.json"
        )

        if transcript_path.exists():

            words = json.loads(
                transcript_path.read_text()
            )

        else:

            print(
                f"  WARNING: transcript file not found:"
            )

            print(
                f"  {transcript_path}"
            )

    # ---------------------------------------------------------
    # Output path
    # ---------------------------------------------------------

    config.HANDOFF_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    out_path = (
        config.HANDOFF_DIR
        / f"{video_id}_handoff.csv"
    )

    # ---------------------------------------------------------
    # CSV columns
    # ---------------------------------------------------------

    fieldnames = [
        # Video / scene
        "video_id",
        "scene_id",
        "start_seconds",
        "end_seconds",
        "topic",

        # Image identity
        "image_id",
        "image_source",
        "image_license",
        "image_title",
        "image_local_path",

        # Image technical information
        "image_width",
        "image_height",
        "image_aspect_ratio",
        "image_quality_score",

        # Validation
        "validation_status",
        "validation_reason",

        # Review
        "needs_review",
        "review_reason",

        # Cache
        "from_cache",

        # Transcript
        "transcript_text",
    ]

    n_flagged = 0
    n_images = 0
    n_passed = 0
    n_failed = 0

    # ---------------------------------------------------------
    # Write CSV
    # ---------------------------------------------------------

    with open(
        out_path,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for a in assignments:

            if a.get("image_id"):
                n_images += 1

            if a.get("needs_review"):
                n_flagged += 1

            if a.get("validation_status") == "PASS":
                n_passed += 1

            if a.get("validation_status") == "FAIL":
                n_failed += 1

            transcript_text = ""

            if config.HANDOFF_INCLUDE_SCENE_TRANSCRIPT_TEXT:

                transcript_text = scene_transcript_text(
                    words,
                    a["start"],
                    a["end"],
                )

            writer.writerow({

                # -------------------------------------------------
                # Video / scene
                # -------------------------------------------------

                "video_id": video_id,

                "scene_id": a["scene_id"],

                "start_seconds": round(
                    a["start"],
                    2,
                ),

                "end_seconds": round(
                    a["end"],
                    2,
                ),

                "topic": a["topic"],

                # -------------------------------------------------
                # Image
                # -------------------------------------------------

                "image_id": (
                    a.get("image_id")
                    or ""
                ),

                "image_source": (
                    a.get("source")
                    or ""
                ),

                "image_license": (
                    a.get("license")
                    or ""
                ),

                "image_title": (
                    a.get("title")
                    or ""
                ),

                "image_local_path": (
                    a.get("local_path")
                    or ""
                ),

                # -------------------------------------------------
                # Image technical information
                # -------------------------------------------------

                "image_width": (
                    a.get("image_width")
                    or ""
                ),

                "image_height": (
                    a.get("image_height")
                    or ""
                ),

                "image_aspect_ratio": (
                    a.get("image_aspect_ratio")
                    or ""
                ),

                "image_quality_score": (
                    a.get("image_quality_score")
                    or ""
                ),

                # -------------------------------------------------
                # Validation
                # -------------------------------------------------

                "validation_status": (
                    a.get("validation_status")
                    or ""
                ),

                "validation_reason": (
                    a.get("validation_reason")
                    or ""
                ),

                # -------------------------------------------------
                # Review
                # -------------------------------------------------

                "needs_review": a.get(
                    "needs_review",
                    False,
                ),

                "review_reason": (
                    a.get("reason")
                    or a.get("validation_reason")
                    or ""
                ),

                # -------------------------------------------------
                # Cache
                # -------------------------------------------------

                "from_cache": a.get(
                    "from_cache",
                    False,
                ),

                # -------------------------------------------------
                # Transcript
                # -------------------------------------------------

                "transcript_text": transcript_text,
            })

    return (
        len(assignments),
        n_flagged,
        n_images,
        n_passed,
        n_failed,
    )


def main(video_id: str = None):

    state.init_db()

    config.HANDOFF_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ---------------------------------------------------------
    # Determine processing queue
    # ---------------------------------------------------------

    queue = state.videos_ready_for(
        "generate_handoff",
        prior_stage="fetch_images",
    )

    if video_id:
        queue = [video_id]

    if not queue:

        print(
            "No videos ready for handoff generation "
            "(need fetch_images = done)."
        )

        return

    summary_rows = []

    # ---------------------------------------------------------
    # Process videos
    # ---------------------------------------------------------

    for vid in queue:

        print(
            f"[handoff] {vid}"
        )

        state.set_status(
            vid,
            "generate_handoff",
            "running",
        )

        try:

            (
                n_scenes,
                n_flagged,
                n_images,
                n_passed,
                n_failed,
            ) = generate_handoff_for_video(vid)

            status = (
                "needs_review"
                if n_flagged > 0
                else "done"
            )

            state.set_status(
                vid,
                "generate_handoff",
                status,
                notes=(
                    f"{n_flagged}/{n_scenes} flagged, "
                    f"{n_images} images, "
                    f"{n_passed} passed, "
                    f"{n_failed} failed"
                ),
            )

            summary_rows.append({

                "video_id": vid,

                "scenes_count": n_scenes,

                "images_assigned": n_images,

                "images_passed_validation": n_passed,

                "images_failed_validation": n_failed,

                "flagged_at_handoff": n_flagged,

                "status": (
                    "READY"
                    if n_flagged == 0
                    else "NEEDS REVIEW"
                ),
            })

        except Exception as e:

            print(
                f"  FAILED: {e}"
            )

            state.set_status(
                vid,
                "generate_handoff",
                "failed",
                notes=str(e),
            )

    # ---------------------------------------------------------
    # Summary CSV
    # ---------------------------------------------------------

    summary_path = (
        config.HANDOFF_DIR
        / "all_videos_summary.csv"
    )

    summary_fields = [
        "video_id",
        "scenes_count",
        "images_assigned",
        "images_passed_validation",
        "images_failed_validation",
        "flagged_at_handoff",
        "status",
    ]

    write_header = not summary_path.exists()

    with open(
        summary_path,
        "a",
        newline="",
        encoding="utf-8",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=summary_fields,
        )

        if write_header:
            writer.writeheader()

        for row in summary_rows:
            writer.writerow(row)

    # ---------------------------------------------------------
    # Final message
    # ---------------------------------------------------------

    print()
    print("=" * 55)
    print("HANDOFF GENERATION COMPLETE")
    print("=" * 55)

    print(
        f"Summary written to:"
    )

    print(
        f"  {summary_path}"
    )

    print("=" * 55)


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