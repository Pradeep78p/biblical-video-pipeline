"""
Step 5B: Validate downloaded/assigned images.

This step does NOT call any image APIs.

It reads the existing:
    data/image_queries/{video_id}_assignments.json

and validates each assigned local image for:

    - file existence
    - image readability
    - width
    - height
    - aspect ratio
    - technical quality score

It updates the assignment records with validation metadata.

Usage:
    python scripts/05b_validate_images.py --video-id CORT_sample_video_2
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.append(str(Path(__file__).parent.parent))

import config


def get_image_info(image_path: str) -> dict | None:
    """
    Read image dimensions and calculate aspect ratio.

    Returns None if the image does not exist or cannot be opened.
    """

    path = Path(image_path)

    if not path.exists():
        return None

    try:
        with Image.open(path) as img:
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
    Score how close the image is to the target aspect ratio.
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


def calculate_quality_score(
    width: int,
    height: int,
    aspect_ratio: float,
) -> float:
    """
    Calculate technical quality score.

    Current weighting:

        60% resolution
        40% aspect ratio
    """

    aspect_score = calculate_aspect_ratio_score(
        aspect_ratio
    )

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


def validate_assignment(assignment: dict) -> dict:
    """
    Validate one image assignment.
    """

    # ---------------------------------------------------------
    # No image assigned
    # ---------------------------------------------------------

    if not assignment.get("image_id"):
        assignment["validation_status"] = "NO_IMAGE"
        assignment["validation_reason"] = assignment.get(
            "reason",
            "No image assigned",
        )
        return assignment

    local_path = assignment.get("local_path")

    if not local_path:
        assignment["validation_status"] = "FAIL"
        assignment["validation_reason"] = (
            "local_path is missing"
        )
        assignment["needs_review"] = True
        return assignment

    # ---------------------------------------------------------
    # Image information
    # ---------------------------------------------------------

    image_info = get_image_info(local_path)

    if image_info is None:

        assignment["validation_status"] = "FAIL"
        assignment["validation_reason"] = (
            "Image does not exist or cannot be opened"
        )
        assignment["needs_review"] = True

        return assignment

    width = image_info["width"]
    height = image_info["height"]
    aspect_ratio = image_info["aspect_ratio"]

    quality_score = calculate_quality_score(
        width,
        height,
        aspect_ratio,
    )

    # ---------------------------------------------------------
    # Store metadata
    # ---------------------------------------------------------

    assignment["image_width"] = width
    assignment["image_height"] = height
    assignment["image_aspect_ratio"] = aspect_ratio
    assignment["image_quality_score"] = quality_score

    # ---------------------------------------------------------
    # Resolution check
    # ---------------------------------------------------------

    resolution_ok = (
        width >= config.MIN_IMAGE_WIDTH
        and height >= config.MIN_IMAGE_HEIGHT
    )

    # ---------------------------------------------------------
    # Quality check
    # ---------------------------------------------------------

    quality_ok = (
        quality_score >= config.MIN_IMAGE_QUALITY_SCORE
    )

    # ---------------------------------------------------------
    # Final validation decision
    # ---------------------------------------------------------

    if resolution_ok and quality_ok:

        assignment["validation_status"] = "PASS"
        assignment["validation_reason"] = (
            "Image passed resolution and technical quality checks"
        )

        # Keep existing review status unless already flagged.
        if not assignment.get("needs_review"):
            assignment["needs_review"] = False

    else:

        assignment["validation_status"] = "FAIL"
        assignment["needs_review"] = True

        reasons = []

        if not resolution_ok:
            reasons.append(
                f"resolution too low: {width}x{height}"
            )

        if not quality_ok:
            reasons.append(
                f"quality score too low: {quality_score}"
            )

        assignment["validation_reason"] = "; ".join(
            reasons
        )

    return assignment


def validate_video(video_id: str):
    """
    Validate all image assignments for one video.
    """

    assignments_path = (
        config.IMAGE_QUERIES_DIR
        / f"{video_id}_assignments.json"
    )

    if not assignments_path.exists():

        print(
            f"ERROR: Assignment file not found:"
        )

        print(
            f"  {assignments_path}"
        )

        return

    print(
        f"[validate_images] {video_id}"
    )

    assignments = json.loads(
        assignments_path.read_text()
    )

    validated_assignments = []

    for assignment in assignments:

        validated = validate_assignment(
            assignment
        )

        validated_assignments.append(
            validated
        )

    # ---------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------

    total = len(validated_assignments)

    images_assigned = sum(
        1
        for a in validated_assignments
        if a.get("image_id")
    )

    passed = sum(
        1
        for a in validated_assignments
        if a.get("validation_status") == "PASS"
    )

    failed = sum(
        1
        for a in validated_assignments
        if a.get("validation_status") == "FAIL"
    )

    no_image = sum(
        1
        for a in validated_assignments
        if a.get("validation_status") == "NO_IMAGE"
    )

    needs_review = sum(
        1
        for a in validated_assignments
        if a.get("needs_review")
    )

    # ---------------------------------------------------------
    # Save updated assignments
    # ---------------------------------------------------------

    assignments_path.write_text(
        json.dumps(
            validated_assignments,
            ensure_ascii=False,
            indent=2,
        )
    )

    # ---------------------------------------------------------
    # Print report
    # ---------------------------------------------------------

    print()
    print("=" * 50)
    print("IMAGE VALIDATION COMPLETE")
    print("=" * 50)

    print(f"Video ID:        {video_id}")
    print(f"Total scenes:    {total}")
    print(f"Images assigned: {images_assigned}")
    print(f"Passed:          {passed}")
    print(f"Failed:          {failed}")
    print(f"No image:        {no_image}")
    print(f"Needs review:    {needs_review}")

    print("=" * 50)

    print(
        f"Updated:"
    )

    print(
        f"  {assignments_path}"
    )


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--video-id",
        required=True,
        help="Video ID to validate",
    )

    args = parser.parse_args()

    validate_video(
        args.video_id
    )


if __name__ == "__main__":
    main()