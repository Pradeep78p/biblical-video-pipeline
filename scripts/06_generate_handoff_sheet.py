"""
Step 6: Compile everything into one clean CSV per video — video ID, scene
chunks with timestamps, assigned image (with unique image ID), and the
transcript text for that scene — ready to hand off to the video editing
team. Opens cleanly in Excel or Google Sheets.

Outputs: data/handoff/{video_id}_handoff.csv
Also writes: data/handoff/all_videos_summary.csv (one row per video, for
tracking which videos are actually ready to hand off)

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
    return " ".join(w["word"].strip() for w in words if start <= w["start"] < end)


def generate_handoff_for_video(video_id: str):
    assignments = json.loads((config.IMAGE_QUERIES_DIR / f"{video_id}_assignments.json").read_text())
    words = []
    if config.HANDOFF_INCLUDE_SCENE_TRANSCRIPT_TEXT:
        words = json.loads((config.TRANSCRIPTS_DIR / f"{video_id}_words.json").read_text())

    out_path = config.HANDOFF_DIR / f"{video_id}_handoff.csv"
    fieldnames = [
        "video_id", "scene_id", "start_seconds", "end_seconds", "topic",
        "image_id", "image_source", "image_license", "image_local_path",
        "needs_review", "review_reason", "transcript_text",
    ]

    n_flagged = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for a in assignments:
            if a["needs_review"]:
                n_flagged += 1
            transcript_text = (
                scene_transcript_text(words, a["start"], a["end"])
                if config.HANDOFF_INCLUDE_SCENE_TRANSCRIPT_TEXT else ""
            )
            writer.writerow({
                "video_id": video_id,
                "scene_id": a["scene_id"],
                "start_seconds": round(a["start"], 2),
                "end_seconds": round(a["end"], 2),
                "topic": a["topic"],
                "image_id": a.get("image_id") or "",
                "image_source": a.get("source") or "",
                "image_license": a.get("license") or "",
                "image_local_path": a.get("local_path") or "",
                "needs_review": a["needs_review"],
                "review_reason": a.get("reason", ""),
                "transcript_text": transcript_text,
            })

    return len(assignments), n_flagged


def main(video_id: str = None):
    state.init_db()
    config.HANDOFF_DIR.mkdir(parents=True, exist_ok=True)

    queue = state.videos_ready_for("generate_handoff", prior_stage="fetch_images")
    if video_id:
        queue = [video_id]

    if not queue:
        print("No videos ready for handoff generation (need fetch_images = done).")
        return

    summary_rows = []
    for vid in queue:
        print(f"[handoff] {vid}")
        state.set_status(vid, "generate_handoff", "running")
        try:
            n_scenes, n_flagged = generate_handoff_for_video(vid)
            status = "needs_review" if n_flagged > 0 else "done"
            state.set_status(vid, "generate_handoff", status, notes=f"{n_flagged}/{n_scenes} flagged")
            summary_rows.append({
                "video_id": vid, "scenes_count": n_scenes,
                "flagged_at_handoff": n_flagged,
                "status": "READY" if n_flagged == 0 else "NEEDS REVIEW",
            })
        except Exception as e:
            print(f"  FAILED: {e}")
            state.set_status(vid, "generate_handoff", "failed", notes=str(e))

    summary_path = config.HANDOFF_DIR / "all_videos_summary.csv"
    write_header = not summary_path.exists()
    with open(summary_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["video_id", "scenes_count", "flagged_at_handoff", "status"])
        if write_header:
            writer.writeheader()
        for row in summary_rows:
            writer.writerow(row)

    print(f"\nSummary written to {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id", default=None)
    args = parser.parse_args()
    main(video_id=args.video_id)
