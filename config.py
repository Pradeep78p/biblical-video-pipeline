"""
Central configuration — every path, key, and threshold in one place.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

ROOT = Path(__file__).parent


# ============================================================
# Data locations
# ============================================================

RAW_VIDEOS_DIR = ROOT / "data" / "raw_videos"
RAW_AUDIO_DIR = ROOT / "data" / "raw_audio"
TRANSCRIPTS_DIR = ROOT / "data" / "transcripts"
SCENE_MANIFESTS_DIR = ROOT / "data" / "scene_manifests"
IMAGE_QUERIES_DIR = ROOT / "data" / "image_queries"
IMAGES_DIR = ROOT / "data" / "images"
HANDOFF_DIR = ROOT / "data" / "handoff"
RENDERED_VIDEOS_DIR = ROOT / "data" / "rendered_videos"

STATE_DB_PATH = ROOT / "pipeline_state.db"


# ============================================================
# API keys
# ============================================================

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")

SMITHSONIAN_API_KEY = os.environ.get("SMITHSONIAN_API_KEY")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")


# ============================================================
# Whisper / transcription
# ============================================================

WHISPER_MODEL_SIZE = "large-v3"

INITIAL_PROMPT_VOCAB = (
    "Yahweh, Elohim, Septuagint, Pentateuch, Torah, Genesis, Exodus, "
    "covenant, exegesis, hermeneutics, soteriology, eschatology, "
    "Messiah, Yeshua, imago Dei, missio Dei"
)


# ============================================================
# Segmentation — Step 3
# ============================================================

SEGMENTATION_WINDOW_SECONDS = 75

SEGMENTATION_WINDOW_OVERLAP_SECONDS = 15

MIN_SCENE_DURATION_SECONDS = 20

CLAUDE_MODEL = "claude-sonnet-4-6"


# ============================================================
# Image sourcing — Steps 4–5
# ============================================================

# Licensed/public-domain image sources.
# NEVER use generic Google/web image search.

IMAGE_SOURCE_PRIORITY = [
    "wikimedia",
    "met_museum",
    "smithsonian",
    "unsplash",
]

MAX_CANDIDATES_PER_SOURCE = 3

IMAGE_DOWNLOAD_TIMEOUT_SECONDS = 20


# ============================================================
# Image quality
# ============================================================

TARGET_VIDEO_WIDTH = 1920

TARGET_VIDEO_HEIGHT = 1080

TARGET_ASPECT_RATIO = TARGET_VIDEO_WIDTH / TARGET_VIDEO_HEIGHT

MIN_IMAGE_WIDTH = 1280

MIN_IMAGE_HEIGHT = 720

# Maximum allowed difference from 16:9
# before an image is considered irregular.

ASPECT_RATIO_TOLERANCE = 0.20

# Minimum quality score for automatic selection.

MIN_IMAGE_QUALITY_SCORE = 60


# ============================================================
# AI Image Expansion — Step 5C
# ============================================================

# Enable Gemini-based expansion of irregular images.

ENABLE_AI_IMAGE_EXPANSION = True

# Gemini is used when the source image is sufficiently
# different from the target 16:9 aspect ratio.

AI_EXPANSION_ASPECT_RATIO_THRESHOLD = 0.25

# Gemini image generation provider.

AI_IMAGE_PROVIDER = "gemini"


# Gemini image model.
#
# This is the image-generation model, NOT a normal text model.

GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image"


# ============================================================
# Video rendering — Step 7
# ============================================================

# Original video:
# 1920x1080 @ 24 FPS

RENDER_WIDTH = 1920

RENDER_HEIGHT = 1080

RENDER_FPS = 24


# Image fitting mode.
#
# "cover":
#     Image fills the target area.
#     Excess portions are cropped.
#
# "blur_background":
#     Image remains intact while the surrounding
#     area is filled with a blurred version.

IMAGE_FIT_MODE = "cover"


# Add subtle movement to static images.

ENABLE_KEN_BURNS = True


# Duration of transitions between scenes.

SCENE_TRANSITION_SECONDS = 0.5


# ============================================================
# Whiteboard placement
# ============================================================

# 1920x1080 tutoring-video layout.
#
# These coordinates define the inner whiteboard/display
# area where the generated/retrieved images are placed.

WHITEBOARD_X = 735

WHITEBOARD_Y = 153

WHITEBOARD_WIDTH = 650

WHITEBOARD_HEIGHT = 363


# ============================================================
# Handoff — Step 6
# ============================================================

HANDOFF_INCLUDE_SCENE_TRANSCRIPT_TEXT = True