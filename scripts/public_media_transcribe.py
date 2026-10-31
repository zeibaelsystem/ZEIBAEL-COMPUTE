#!/usr/bin/env python3
"""Free, CPU-only, no-account transcription of already extracted PUBLIC media.

No remote paid API, user credentials, or production secrets. Public runner outputs
may be visible, so never use this job for private or sensitive uploads.
"""
import json
import os
import signal
from pathlib import Path

def serialize_transcript(segments, info):
    rows = [{"start": round(float(s.start), 2), "end": round(float(s.end), 2),
             "text": str(s.text).strip()} for s in segments
            if str(s.text).strip()]
    text = " ".join(row["text"] for row in rows)
    return {"schema": 1, "engine": "faster-whisper-base/cpu-int8",
            "status": "transcribed" if rows else "no_recognized_speech",
            "language": getattr(info, "language", None),
            "language_probability": round(float(getattr(info, "language_probability", 0)), 3),
            "text": text[:12000], "segments": rows[:120]}

def main():
    root = Path(os.environ["ZEIBAEL_OUTPUT_DIR"]) / "files"
    audio = root / "speech.wav"
    if not audio.is_file() or audio.is_symlink() or audio.stat().st_size > 3_000_000:
        return 0
    status_file = root / "transcript.json"
    def timeout_handler(*_):
        raise TimeoutError("ASR budget exceeded")
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(240)
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("Systran/faster-whisper-base",
                             device="cpu", compute_type="int8",
                             cpu_threads=2, num_workers=1)
        segments, info = model.transcribe(
            str(audio), beam_size=3, vad_filter=True,
            condition_on_previous_text=False)
        result = serialize_transcript(segments, info)
    except Exception:
        # No provider errors or signed URLs in public job logs.
        result = {"schema": 1, "engine": "faster-whisper-base/cpu-int8",
                  "status": "asr_unavailable", "text": "", "segments": []}
    finally:
        signal.alarm(0)
    status_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("ZEIBAEL_PUBLIC_ASR_STATUS=" + result["status"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
