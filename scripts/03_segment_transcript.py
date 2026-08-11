"""
Step 3: Segment each video's transcript into meaningful topical scenes,
each with precise timestamps and a UNIQUE SCENE ID.

Chunks the transcript into overlapping windows, asks Claude for scenes in
each window (via tool use), merges overlapping/duplicate scenes across
windows, and enforces a minimum scene duration.

Outputs: data/scene_manifests/{video_id}_scenes.json
Format: [{"scene_id": "sermon_042_s001", "start": 12.3, "end": 45.6,
          "topic": "...", "biblical_reference": "Genesis 2:7"}]

Usage:
    python scripts/03_segment_transcript.py
    python scripts/03_segment_transcript.py --video-id sermon_042
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
import config
import pipeline_state as state

SCENE_TOOL = {
    "name": "record_scenes",
    "description": "Record the distinct topical scenes identified in this transcript window.",
    "input_schema": {
        "type": "object",
        "properties": {
            "scenes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "number", "description": "Scene start time in seconds"},
                        "end": {"type": "number", "description": "Scene end time in seconds"},
                        "topic": {"type": "string", "description": "Short topic label, e.g. 'Genesis 2 — creation of Adam'"},
                        "biblical_reference": {"type": "string", "description": "Scripture reference if applicable, else empty string"},
                    },
                    "required": ["start", "end", "topic", "biblical_reference"],
                },
            }
        },
        "required": ["scenes"],
    },
}

SYSTEM_PROMPT = """You are analyzing a transcript excerpt from a Christian biblical theology \
teaching video. Identify distinct topical scenes within this window — points where the \
teacher shifts to a new story, concept, place, or scripture passage. Use the record_scenes \
tool to report them. Do not invent timestamps outside the window given."""


def load_words(video_id: str) -> list:
    path = config.TRANSCRIPTS_DIR / f"{video_id}_words.json"
    return json.loads(path.read_text())


def make_windows(words: list) -> list:
    if not words:
        return []
    total_end = words[-1]["end"]
    windows = []
    t = 0.0
    while t < total_end:
        w_end = t + config.SEGMENTATION_WINDOW_SECONDS
        window_words = [w for w in words if t <= w["start"] < w_end]
        if window_words:
            windows.append((t, w_end, window_words))
        t += config.SEGMENTATION_WINDOW_SECONDS - config.SEGMENTATION_WINDOW_OVERLAP_SECONDS
    return windows


def call_claude_for_window(client, window_words: list, window_start: float, window_end: float) -> list:
    transcript_text = " ".join(w["word"] for w in window_words)
    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        tools=[SCENE_TOOL],
        tool_choice={"type": "tool", "name": "record_scenes"},
        messages=[{
            "role": "user",
            "content": f"Transcript window [{window_start:.1f}s - {window_end:.1f}s]:\n\n{transcript_text}",
        }],
    )
    for block in message.content:
        if block.type == "tool_use" and block.name == "record_scenes":
            return block.input.get("scenes", [])
    return []


def merge_scenes(all_scenes: list) -> list:
    all_scenes = sorted(all_scenes, key=lambda s: s["start"])
    merged = []
    for scene in all_scenes:
        if merged and scene["start"] < merged[-1]["end"] - 5:
            continue
        if scene["end"] - scene["start"] < config.MIN_SCENE_DURATION_SECONDS and merged:
            merged[-1]["end"] = scene["end"]
            continue
        merged.append(scene)
    return merged


def assign_scene_ids(video_id: str, scenes: list) -> list:
    for i, scene in enumerate(scenes, start=1):
        scene["scene_id"] = f"{video_id}_s{i:03d}"
    return scenes


def segment_video(client, video_id: str):
    words = load_words(video_id)
    windows = make_windows(words)

    all_scenes = []
    for w_start, w_end, window_words in windows:
        scenes = call_claude_for_window(client, window_words, w_start, w_end)
        all_scenes.extend(scenes)

    merged = merge_scenes(all_scenes)
    return assign_scene_ids(video_id, merged)


def main(video_id: str = None):
    from anthropic import Anthropic

    state.init_db()
    config.SCENE_MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    if not config.ANTHROPIC_API_KEY:
        print("Set ANTHROPIC_API_KEY in your environment (.env file) before running this stage.")
        return
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

    queue = state.videos_ready_for("segment", prior_stage="transcribe")
    if video_id:
        queue = [video_id]

    if not queue:
        print("No videos ready for segmentation (need transcribe = done).")
        return

    for vid in queue:
        out_path = config.SCENE_MANIFESTS_DIR / f"{vid}_scenes.json"
        if out_path.exists():
            print(f"[skip] {vid} — scene manifest already exists")
            state.set_status(vid, "segment", "done")
            continue

        print(f"[segment] {vid}")
        state.set_status(vid, "segment", "running")
        try:
            scenes = segment_video(client, vid)
            out_path.write_text(json.dumps(scenes, ensure_ascii=False, indent=2))
            state.set_status(vid, "segment", "done", notes=f"{len(scenes)} scenes")
        except Exception as e:
            print(f"  FAILED: {e}")
            state.set_status(vid, "segment", "failed", notes=str(e))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id", default=None)
    args = parser.parse_args()
    main(video_id=args.video_id)
