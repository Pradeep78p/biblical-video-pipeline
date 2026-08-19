"""
Step 5C: AI image expansion using Gemini.

For images that are significantly different from 16:9, Gemini is used to
expand the surrounding background while preserving the original subject.

The original downloaded image is NEVER overwritten.

Outputs:
    data/images/{image_id}_expanded.jpg

The assignment JSON is updated so later steps can use the expanded image.

Usage:
    python scripts/05c_expand_images.py --video-id CORT_sample_video_2
"""

import argparse
import base64
import json
import mimetypes
import sys
from pathlib import Path

from PIL import Image

# Allow imports from project root
sys.path.append(str(Path(__file__).parent.parent))

import config


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

try:
    from google import genai
except ImportError:
    genai = None


GEMINI_MODEL = "gemini-3.1-flash-image"


# ---------------------------------------------------------------------------
# Image utilities
# ---------------------------------------------------------------------------

def get_image_dimensions(image_path: Path):
    """
    Return width, height, and aspect ratio.
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size

        if height == 0:
            return None

        return {
            "width": width,
            "height": height,
            "aspect_ratio": width / height,
        }

    except Exception as e:
        print(f"  [warning] Could not inspect image: {image_path}")
        print(f"  Reason: {e}")
        return None


def should_expand(aspect_ratio: float) -> bool:
    """
    Decide whether an image is sufficiently different from 16:9
    to justify Gemini expansion.

    Example:
        16:9  -> approximately 1.777 -> no expansion
        4:3   -> 1.333 -> expansion
        3:2   -> 1.500 -> expansion
        9:16  -> 0.562 -> expansion
    """

    target = config.TARGET_ASPECT_RATIO

    difference = abs(aspect_ratio - target)

    return difference > config.AI_EXPANSION_ASPECT_RATIO_THRESHOLD


def get_mime_type(image_path: Path) -> str:
    """
    Determine MIME type for Gemini input.
    """
    mime_type, _ = mimetypes.guess_type(str(image_path))

    if mime_type:
        return mime_type

    return "image/jpeg"


# ---------------------------------------------------------------------------
# Gemini image expansion
# ---------------------------------------------------------------------------

def expand_image_with_gemini(
    image_path: Path,
    output_path: Path,
) -> bool:
    """
    Send an image to Gemini and ask it to expand the surrounding background
    into a 16:9 composition.

    Returns:
        True  -> successful
        False -> failed
    """

    if not config.GEMINI_API_KEY:
        print("  ERROR: GEMINI_API_KEY is not configured.")
        print("  Check your .env file.")
        return False

    if genai is None:
        print("  ERROR: google-genai is not installed.")
        print("  Run:")
        print("      pip install google-genai")
        return False

    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)

        image_bytes = image_path.read_bytes()
        mime_type = get_mime_type(image_path)

        prompt = """
Expand the provided image into a natural 16:9 widescreen composition.

IMPORTANT INSTRUCTIONS:

1. Preserve the original main subject exactly.
2. Do NOT stretch, deform, replace, or redesign the main subject.
3. Do NOT remove important details from the original subject.
4. Extend only the surrounding background/environment naturally.
5. Match the original lighting, colors, texture, perspective, and visual style.
6. The newly generated background should look like it naturally continues
   from the original image.
7. Do not introduce unrelated objects.
8. Do not add text, captions, labels, logos, watermarks, or borders.
9. The result should look like a natural wider version of the original image.
10. The final composition must be suitable for displaying on a 16:9
    educational video whiteboard.

For example, if the original image contains a narrow ancient artifact,
pot, person, building, or historical object, keep that object intact and
expand the surrounding environment rather than stretching or cropping it.

Return the edited image.
""".strip()

        print(f"  Sending image to Gemini: {image_path.name}")

        # Current Gemini image editing API.
        interaction = client.interactions.create(
            model=GEMINI_MODEL,
            input=[
                {
                    "type": "text",
                    "text": prompt,
                },
                {
                    "type": "image",
                    "data": base64.b64encode(image_bytes).decode("utf-8"),
                    "mime_type": mime_type,
                },
            ],
            response_format={
                "type": "image",
                "mime_type": "image/jpeg",
                "aspect_ratio": "16:9",
                "image_size": "1K",
            },
        )

        # Look for generated image output.
        output_image = getattr(interaction, "output_image", None)

        if output_image is None:
            print("  ERROR: Gemini returned no image.")
            return False

        image_data = getattr(output_image, "data", None)

        if not image_data:
            print("  ERROR: Gemini returned empty image data.")
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_path.write_bytes(
            base64.b64decode(image_data)
        )

        print(f"  Expanded image saved: {output_path}")

        return True

    except Exception as e:
        print("  ERROR: Gemini image expansion failed.")
        print(f"  Reason: {e}")
        return False


# ---------------------------------------------------------------------------
# Process one assignment
# ---------------------------------------------------------------------------

def process_assignment(assignment: dict) -> dict:
    """
    Process one image assignment.

    If the image is already suitable, keep the original.

    If it is irregular, attempt Gemini expansion.
    """

    image_id = assignment.get("image_id")

    if not image_id:
        return assignment

    local_path = assignment.get("local_path")

    if not local_path:
        assignment["ai_expansion_status"] = "skipped"
        assignment["ai_expansion_reason"] = "no local image path"
        return assignment

    image_path = Path(local_path)

    if not image_path.exists():
        assignment["ai_expansion_status"] = "failed"
        assignment["ai_expansion_reason"] = "original image file not found"
        return assignment

    # Inspect original image.
    info = get_image_dimensions(image_path)

    if info is None:
        assignment["ai_expansion_status"] = "failed"
        assignment["ai_expansion_reason"] = "could not read image"
        return assignment

    width = info["width"]
    height = info["height"]
    aspect_ratio = info["aspect_ratio"]

    assignment["original_width"] = width
    assignment["original_height"] = height
    assignment["original_aspect_ratio"] = round(aspect_ratio, 4)

    print(
        f"\n  Image: {image_id}"
        f"\n  Size: {width}x{height}"
        f"\n  Aspect ratio: {aspect_ratio:.4f}"
    )

    # Already suitable.
    if not should_expand(aspect_ratio):
        print("  → Image is sufficiently close to 16:9.")
        print("  → Gemini expansion not required.")

        assignment["ai_expansion_status"] = "not_needed"
        assignment["processed_local_path"] = str(image_path)
        assignment["processed_image_id"] = image_id
        assignment["processed_aspect_ratio"] = round(aspect_ratio, 4)

        return assignment

    print("  → Image is significantly different from 16:9.")
    print("  → Gemini expansion required.")

    expanded_path = (
        config.IMAGES_DIR /
        f"{image_id}_expanded.jpg"
    )

    # Reuse existing expansion if it already exists.
    if expanded_path.exists():
        print("  → Expanded image already exists. Reusing it.")

        expanded_info = get_image_dimensions(expanded_path)

        assignment["ai_expansion_status"] = "reused"
        assignment["processed_local_path"] = str(expanded_path)
        assignment["processed_image_id"] = f"{image_id}_expanded"

        if expanded_info:
            assignment["processed_width"] = expanded_info["width"]
            assignment["processed_height"] = expanded_info["height"]
            assignment["processed_aspect_ratio"] = round(
                expanded_info["aspect_ratio"],
                4,
            )

        return assignment

    # Generate expanded image.
    success = expand_image_with_gemini(
        image_path=image_path,
        output_path=expanded_path,
    )

    if not success:
        print("  → Keeping original image because Gemini expansion failed.")

        assignment["ai_expansion_status"] = "failed"
        assignment["processed_local_path"] = str(image_path)
        assignment["processed_image_id"] = image_id

        return assignment

    # Inspect generated image.
    expanded_info = get_image_dimensions(expanded_path)

    assignment["ai_expansion_status"] = "generated"
    assignment["processed_local_path"] = str(expanded_path)
    assignment["processed_image_id"] = f"{image_id}_expanded"

    if expanded_info:
        assignment["processed_width"] = expanded_info["width"]
        assignment["processed_height"] = expanded_info["height"]
        assignment["processed_aspect_ratio"] = round(
            expanded_info["aspect_ratio"],
            4,
        )

    return assignment


# ---------------------------------------------------------------------------
# Process video
# ---------------------------------------------------------------------------

def expand_images_for_video(video_id: str):
    """
    Load Step 5 assignments and process their images.
    """

    assignments_path = (
        config.IMAGE_QUERIES_DIR /
        f"{video_id}_assignments.json"
    )

    if not assignments_path.exists():
        print("ERROR: Assignment file not found:")
        print(f"  {assignments_path}")
        print()
        print("Run Step 5 first:")
        print(f"  python scripts/05_fetch_images.py --video-id {video_id}")
        return False

    assignments = json.loads(
        assignments_path.read_text(encoding="utf-8")
    )

    print("=" * 60)
    print("STEP 5C — GEMINI IMAGE EXPANSION")
    print("=" * 60)
    print(f"Video ID: {video_id}")
    print(f"Scenes: {len(assignments)}")
    print()

    processed = []

    stats = {
        "total": 0,
        "no_image": 0,
        "not_needed": 0,
        "generated": 0,
        "reused": 0,
        "failed": 0,
    }

    for assignment in assignments:

        if not assignment.get("image_id"):
            stats["no_image"] += 1
            processed.append(assignment)
            continue

        stats["total"] += 1

        result = process_assignment(assignment)

        status = result.get("ai_expansion_status")

        if status == "not_needed":
            stats["not_needed"] += 1

        elif status == "generated":
            stats["generated"] += 1

        elif status == "reused":
            stats["reused"] += 1

        elif status == "failed":
            stats["failed"] += 1

        processed.append(result)

    # Save updated assignments.
    assignments_path.write_text(
        json.dumps(
            processed,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("STEP 5C COMPLETE")
    print("=" * 60)

    print(f"Images processed:       {stats['total']}")
    print(f"No image:               {stats['no_image']}")
    print(f"Already suitable:       {stats['not_needed']}")
    print(f"Gemini generated:       {stats['generated']}")
    print(f"Previously generated:   {stats['reused']}")
    print(f"Expansion failed:       {stats['failed']}")

    print()
    print(f"Updated assignments:")
    print(assignments_path)

    print("=" * 60)

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--video-id",
        required=True,
        help="Video ID to process",
    )

    args = parser.parse_args()

    if not config.ENABLE_AI_IMAGE_EXPANSION:
        print("AI image expansion is disabled in config.py.")
        print()
        print("Set:")
        print("  ENABLE_AI_IMAGE_EXPANSION = True")
        return

    if not config.GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY was not found.")
        print()
        print("Make sure your .env contains:")
        print()
        print("GEMINI_API_KEY=your_key_here")
        return

    expand_images_for_video(args.video_id)


if __name__ == "__main__":
    main()