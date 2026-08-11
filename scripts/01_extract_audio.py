"""
Step 1: Extract audio from every video in data/raw_videos/ using ffmpeg.
Stores WAV files named by unique video_id in data/raw_audio/.

Usage:
    python scripts/01_extract_audio.py
    python scripts/01_extract_audio.py --video-id sermon_042
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
import config
import pipeline_state as state


def extract_audio(video_path: Path, out_path: Path):
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-ar", "16000", "-ac", "1", "-vn",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {video_path.name}:\n{result.stderr[-2000:]}")


def main(video_id: str = None):
    state.init_db()
    config.RAW_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    video_files = list(config.RAW_VIDEOS_DIR.glob("*.mp4"))
    if video_id:
        video_files = [v for v in video_files if v.stem == video_id]

    if not video_files:
        print(f"No videos found in {config.RAW_VIDEOS_DIR} (looking for .mp4)")
        return

    for video_path in video_files:
        vid = video_path.stem  # this becomes the unique video_id used everywhere downstream
        state.register_video(vid)
        out_path = config.RAW_AUDIO_DIR / f"{vid}.wav"

        if out_path.exists():
            print(f"[skip] {vid} — audio already extracted")
            state.set_status(vid, "extract_audio", "done")
            continue

        print(f"[extract] {vid}")
        state.set_status(vid, "extract_audio", "running")
        try:
            extract_audio(video_path, out_path)
            state.set_status(vid, "extract_audio", "done")
        except Exception as e:
            print(f"  FAILED: {e}")
            state.set_status(vid, "extract_audio", "failed", notes=str(e))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id", default=None)
    args = parser.parse_args()
    main(video_id=args.video_id)
