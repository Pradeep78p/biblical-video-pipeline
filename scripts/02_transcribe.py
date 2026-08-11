"""
Step 2: Transcribe audio with WhisperX (large-v3 model), producing
word-level timestamps. Stored per unique video_id.

Outputs: data/transcripts/{video_id}_words.json
Format: [{"word": "...", "start": 12.34, "end": 12.58}, ...]

Usage:
    python scripts/02_transcribe.py
    python scripts/02_transcribe.py --video-id sermon_042
    python scripts/02_transcribe.py --device cpu
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
import config
import pipeline_state as state


def transcribe_one(audio_path: Path, device: str) -> list:
    import whisperx

    model = whisperx.load_model(
        config.WHISPER_MODEL_SIZE,
        device=device,
        compute_type="float16" if device == "cuda" else "int8",
        asr_options={"initial_prompt": config.INITIAL_PROMPT_VOCAB},
    )
    audio = whisperx.load_audio(str(audio_path))
    result = model.transcribe(audio, batch_size=16)

    align_model, metadata = whisperx.load_align_model(
        language_code=result["language"], device=device
    )
    aligned = whisperx.align(result["segments"], align_model, metadata, audio, device)

    words = []
    for seg in aligned["segments"]:
        for w in seg.get("words", []):
            if "start" in w and "end" in w:
                words.append({"word": w["word"], "start": w["start"], "end": w["end"]})
    return words


def main(video_id: str = None, device: str = "cuda"):
    state.init_db()
    config.TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    queue = state.videos_ready_for("transcribe", prior_stage="extract_audio")
    if video_id:
        queue = [video_id]

    if not queue:
        print("No videos ready for transcription (need extract_audio = done).")
        return

    for vid in queue:
        audio_path = config.RAW_AUDIO_DIR / f"{vid}.wav"
        out_path = config.TRANSCRIPTS_DIR / f"{vid}_words.json"

        if out_path.exists():
            print(f"[skip] {vid} — transcript already exists")
            state.set_status(vid, "transcribe", "done")
            continue

        print(f"[transcribe] {vid}")
        state.set_status(vid, "transcribe", "running")
        try:
            words = transcribe_one(audio_path, device)
            out_path.write_text(json.dumps(words, ensure_ascii=False, indent=2))
            state.set_status(vid, "transcribe", "done")
        except Exception as e:
            print(f"  FAILED: {e}")
            state.set_status(vid, "transcribe", "failed", notes=str(e))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id", default=None)
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    args = parser.parse_args()
    main(video_id=args.video_id, device=args.device)
