"""
Step 4: For each scene from Step 3, ask Claude: does this scene warrant an
image, and if so, what should we search for? This keeps "should we show a
picture here" and "what should it be" as an explicit decision, separate
from topic segmentation itself.

Outputs: data/image_queries/{video_id}_queries.json
Format: [{"scene_id": "...", "start":.., "end":.., "needs_image": true,
          "search_query": "Egypt Nile river ancient landscape"}]

Usage:
    python scripts/04_generate_image_queries.py
    python scripts/04_generate_image_queries.py --video-id sermon_042
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
import config
import pipeline_state as state

QUERY_TOOL = {
    "name": "record_image_decisions",
    "description": "Record whether each scene needs an image and, if so, a concrete search query.",
    "input_schema": {
        "type": "object",
        "properties": {
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "scene_id": {"type": "string"},
                        "needs_image": {"type": "boolean"},
                        "search_query": {
                            "type": "string",
                            "description": "Concrete, literal search query for a public-domain image site (empty string if needs_image is false)",
                        },
                    },
                    "required": ["scene_id", "needs_image", "search_query"],
                },
            }
        },
        "required": ["decisions"],
    },
}

SYSTEM_PROMPT = """You are deciding which scenes in a biblical theology teaching video should \
be illustrated with an image, and what to search for. Not every scene needs one — skip scenes \
that are abstract doctrinal discussion with no concrete visual referent. For scenes that DO \
warrant an image (a named story, place, person, or event), write a concrete, literal search \
query suitable for searching a museum/public-domain image archive (e.g. "creation of Adam \
Genesis painting", "ancient Egypt Nile river landscape", "Red Sea crossing Exodus"). Use the \
record_image_decisions tool."""


def call_claude(client, scenes: list) -> list:
    payload = [
        {"scene_id": s["scene_id"], "topic": s["topic"], "biblical_reference": s.get("biblical_reference", "")}
        for s in scenes
    ]
    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        tools=[QUERY_TOOL],
        tool_choice={"type": "tool", "name": "record_image_decisions"},
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    for block in message.content:
        if block.type == "tool_use" and block.name == "record_image_decisions":
            return block.input.get("decisions", [])
    return []


def generate_queries_for_video(client, video_id: str) -> list:
    scenes = json.loads((config.SCENE_MANIFESTS_DIR / f"{video_id}_scenes.json").read_text())
    decisions = call_claude(client, scenes)
    decisions_by_id = {d["scene_id"]: d for d in decisions}

    result = []
    for scene in scenes:
        d = decisions_by_id.get(scene["scene_id"], {"needs_image": False, "search_query": ""})
        result.append({
            "scene_id": scene["scene_id"],
            "start": scene["start"],
            "end": scene["end"],
            "topic": scene["topic"],
            "needs_image": d.get("needs_image", False),
            "search_query": d.get("search_query", ""),
        })
    return result


def main(video_id: str = None):
    from anthropic import Anthropic

    state.init_db()
    config.IMAGE_QUERIES_DIR.mkdir(parents=True, exist_ok=True)

    if not config.ANTHROPIC_API_KEY:
        print("Set ANTHROPIC_API_KEY in your environment (.env file) before running this stage.")
        return
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

    queue = state.videos_ready_for("generate_image_queries", prior_stage="segment")
    if video_id:
        queue = [video_id]

    if not queue:
        print("No videos ready for image query generation (need segment = done).")
        return

    for vid in queue:
        out_path = config.IMAGE_QUERIES_DIR / f"{vid}_queries.json"
        if out_path.exists():
            print(f"[skip] {vid} — image queries already exist")
            state.set_status(vid, "generate_image_queries", "done")
            continue

        print(f"[image_queries] {vid}")
        state.set_status(vid, "generate_image_queries", "running")
        try:
            queries = generate_queries_for_video(client, vid)
            out_path.write_text(json.dumps(queries, ensure_ascii=False, indent=2))
            n_needed = sum(1 for q in queries if q["needs_image"])
            state.set_status(vid, "generate_image_queries", "done", notes=f"{n_needed}/{len(queries)} scenes need images")
        except Exception as e:
            print(f"  FAILED: {e}")
            state.set_status(vid, "generate_image_queries", "failed", notes=str(e))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id", default=None)
    args = parser.parse_args()
    main(video_id=args.video_id)
