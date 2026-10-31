#!/usr/bin/env python3
"""Free, CPU-only, no-account transcription of already extracted PUBLIC media.

No remote paid API, user credentials, or production secrets. Public runner outputs
may be visible, so never use this job for private or sensitive uploads.
"""
import json
import os
import signal
import re
import traceback
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

def transcribe_with_fallback(model, source):
    """Retry without VAD on a typed local decoder/VAD API incompatibility."""
    try:
        a, b = model.transcribe(source, beam_size=3, vad_filter=True,
                                condition_on_previous_text=False)
        return a, b, False
    except TypeError:
        a, b = model.transcribe(source, beam_size=3, vad_filter=False,
                                language="id", condition_on_previous_text=False)
        return a, b, True

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
    stage = "model_init"
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("Systran/faster-whisper-base",
                             device="cpu", compute_type="int8",
                             cpu_threads=2, num_workers=1)
        stage = "transcribe"
        segments, info, fallback_used = transcribe_with_fallback(model, str(audio))
        stage = "serialize"
        result = serialize_transcript(segments, info)
        result["no_vad_fallback_used"] = fallback_used
    except Exception as exc:
        # Safe diagnostics only: class name and HTTP status. Never raw exception
        # messages, because remote fetch errors may include token-bearing URLs.
        status = getattr(getattr(exc, "response", None), "status_code", None)
        # Only short local type-error descriptions; strip URLs, paths and tokens.
        message = str(exc)
        safe_message = (message[:180] if len(message) < 181 and
                        re.fullmatch(r"[A-Za-z0-9 .,:_()\x27-]+", message) and
                        not any(x in message.lower() for x in ("token", "secret", "https", "key"))
                        else "REDACTED")
        stack = [frame.name for frame in traceback.extract_tb(exc.__traceback__)[-5:]]
        result = {"schema": 1, "engine": "faster-whisper-base/cpu-int8",
                  "status": "asr_unavailable", "text": "", "segments": [],
                  "failure_stage": stage, "failure_type": type(exc).__name__,
                  "http_status": status if isinstance(status, int) else None,
                  "failure_message": safe_message,
                  "failure_stack": stack}
    finally:
        signal.alarm(0)
    status_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("ZEIBAEL_PUBLIC_ASR_STATUS=" + result["status"])
    if result["status"] == "asr_unavailable":
        print("ZEIBAEL_PUBLIC_ASR_DIAG stage=%s type=%s http=%s" %
              (result["failure_stage"], result["failure_type"], result["http_status"]))
        print("ZEIBAEL_PUBLIC_ASR_SAFE_DETAIL=" + result["failure_message"])
        print("ZEIBAEL_PUBLIC_ASR_SAFE_STACK=" + ",".join(result["failure_stack"]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
