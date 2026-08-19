"""
Central configuration — every path, key, and threshold in one place.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent

# --- Data locations ---
RAW_VIDEOS_DIR = ROOT / "data" / "raw_videos"
RAW_AUDIO_DIR = ROOT / "data" / "raw_audio"
TRANSCRIPTS_DIR = ROOT / "data" / "transcripts"
SCENE_MANIFESTS_DIR = ROOT / "data" / "scene_manifests"
IMAGE_QUERIES_DIR = ROOT / "data" / "image_queries"
IMAGES_DIR = ROOT / "data" / "images"              # downloaded image files, named by unique image_id
HANDOFF_DIR = ROOT / "data" / "handoff"

STATE_DB_PATH = ROOT / "pipeline_state.db"          # also holds the query cache table

# --- API keys (read from environment / .env) ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")        # optional, for landscape/backdrop photos
SMITHSONIAN_API_KEY = os.environ.get("SMITHSONIAN_API_KEY")        # optional, get free key at api.data.gov
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- Whisper / transcription ---
WHISPER_MODEL_SIZE = "large-v3"
INITIAL_PROMPT_VOCAB = (
    "Yahweh, Elohim, Septuagint, Pentateuch, Torah, Genesis, Exodus, "
    "covenant, exegesis, hermeneutics, soteriology, eschatology, "
    "Messiah, Yeshua, imago Dei, missio Dei"
)

# --- Segmentation (Step 3) ---
SEGMENTATION_WINDOW_SECONDS = 75
SEGMENTATION_WINDOW_OVERLAP_SECONDS = 15
MIN_SCENE_DURATION_SECONDS = 20
CLAUDE_MODEL = "claude-sonnet-4-6"

# --- Image sourcing (Steps 4-5) ---
# Priority order of licensed sources to try, per scene, until a usable image is found.
# All of these are public-domain / CC0 / free-to-use — NEVER generic web/Google Images.
IMAGE_SOURCE_PRIORITY = ["wikimedia", "met_museum", "smithsonian", "unsplash"]
MAX_CANDIDATES_PER_SOURCE = 3
IMAGE_DOWNLOAD_TIMEOUT_SECONDS = 20

# --- Handoff (Step 6) ---
HANDOFF_INCLUDE_SCENE_TRANSCRIPT_TEXT = True

# --- Image quality ---

TARGET_VIDEO_WIDTH = 1920
TARGET_VIDEO_HEIGHT = 1080
TARGET_ASPECT_RATIO = TARGET_VIDEO_WIDTH / TARGET_VIDEO_HEIGHT

MIN_IMAGE_WIDTH = 1280
MIN_IMAGE_HEIGHT = 720

# Prefer images close to 16:9, but do not require exact 16:9.
ASPECT_RATIO_TOLERANCE = 0.20

# Minimum quality score required for automatic selection.
MIN_IMAGE_QUALITY_SCORE = 60



# --- AI image processing ---

# Expand irregular/portrait images to 16:9 using Gemini.
ENABLE_AI_IMAGE_EXPANSION = True

# Only use Gemini when the image is sufficiently far from 16:9.
AI_EXPANSION_ASPECT_RATIO_THRESHOLD = 0.25

AI_IMAGE_PROVIDER = "gemini"


# --- Video rendering ---

# Your original video is 1920x1080 at 24 FPS.
RENDER_WIDTH = 1920
RENDER_HEIGHT = 1080
RENDER_FPS = 24

# Image fitting mode.
# "cover" = fill the target area and crop excess.
# "blur_background" = useful for portrait images.
IMAGE_FIT_MODE = "cover"

# Add subtle movement to static images.
ENABLE_KEN_BURNS = True

# Duration of transitions between scene images.
SCENE_TRANSITION_SECONDS = 0.5


# --- Whiteboard placement ---
# Coordinates are based on the 1920x1080 tutoring-video layout.
# These define the INNER whiteboard/display area where images are placed.

WHITEBOARD_X = 735
WHITEBOARD_Y = 153
WHITEBOARD_WIDTH = 650
WHITEBOARD_HEIGHT = 363


# --- Rendered videos ---Get-Content scripts\05_fetch_images.py
# --- Rendered videos ---
RENDERED_VIDEOS_DIR = ROOT / "data" / "rendered_videos"
