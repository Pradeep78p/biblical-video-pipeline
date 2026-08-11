"""
Central configuration — every path, key, and threshold in one place.
"""
import os
from pathlib import Path

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
