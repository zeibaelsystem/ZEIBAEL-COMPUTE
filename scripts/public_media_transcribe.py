#!/usr/bin/env python3
"""Free, CPU-only, no-account transcription of already extracted PUBLIC media.

No remote paid API, user credentials, or production secrets. Public runner outputs
may be visible, so never use this job for private or sensitive uploads.
"""
import json
import os
import signal
import wave
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
            "text": text[:60000], "segments": rows[:800], "transcript_truncated": len(rows) > 800 or len(text) > 60000}

def compact_public_transcript(result):
    """One-line public-speech evidence for orchestration; treat text as untrusted."""
    state = result.get("status", "asr_unavailable")
    if state not in ("transcribed", "transcribed_partial_coverage", "no_recognized_speech", "asr_unavailable"):
        state = "asr_unavailable"
    payload = {"status": state,
               "language": result.get("language") if state in ("transcribed", "transcribed_partial_coverage") else None,
               "text": str(result.get("text") or "")[:1600] if state in ("transcribed", "transcribed_partial_coverage") else ""}
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def read_pcm16_mono(path):
    """Convert owned FFmpeg PCM16 WAV to float32; bypass fragile PyAV open()."""
    import numpy as np
    with wave.open(str(path), "rb") as reader:
        if (reader.getnchannels() != 1 or reader.getframerate() != 16000
                or reader.getsampwidth() != 2 or reader.getcomptype() != "NONE"):
            raise ValueError("Expected 16 kHz mono PCM16 WAV")
        raw = reader.readframes(min(reader.getnframes(), 55 * 16000))
    if len(raw) < 1600 or len(raw) % 2:
        raise ValueError("Truncated or empty WAV input")
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0

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
    full_audio = root / "speech_full.opus"
    legacy_audio = root / "speech.wav"
    audio = full_audio if (full_audio.is_file() and not full_audio.is_symlink()
                           and full_audio.stat().st_size <= 12_000_000) else legacy_audio
    if not audio.is_file() or audio.is_symlink() or audio.stat().st_size > 12_000_000:
        try:
            from scripts.public_video_timeline import write_timeline
        except ModuleNotFoundError:
            from public_video_timeline import write_timeline
        write_timeline(root, {"status": "no_audio", "segments": []})
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
        if audio.suffix == ".opus":
            try:
                from scripts.public_video_timeline import transcribe_full
            except ModuleNotFoundError:
                from public_video_timeline import transcribe_full
            meta = json.loads((root / "media-result.json").read_text(encoding="utf-8"))
            seconds = float(meta.get("coverage", {}).get("audio_seconds_available") or 0)
            stage = "transcribe_full_window"
            result = transcribe_full(model, audio, seconds,
                                     read_pcm16_mono, transcribe_with_fallback,
                                     serialize_transcript)
            if float(meta.get("duration_seconds") or 0) > seconds:
                if result["status"] == "transcribed":
                    result["status"] = "transcribed_partial_coverage"
        else:
            stage = "read_pcm"
            samples = read_pcm16_mono(audio)
            stage = "transcribe"
            segments, info, fallback_used = transcribe_with_fallback(model, samples)
            stage = "serialize"
            result = serialize_transcript(segments, info)
            result["no_vad_fallback_used"] = fallback_used
            meta_path = root / "media-result.json"
            if meta_path.is_file():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if float(meta.get("duration_seconds") or 0) > 55:
                    if result["status"] == "transcribed":
                        result["status"] = "transcribed_partial_coverage"
                result["audio_coverage_seconds"] = min(55, float(meta.get("duration_seconds") or 0))
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
    try:
        from scripts.public_video_timeline import write_timeline
    except ModuleNotFoundError:
        from public_video_timeline import write_timeline
    write_timeline(root, result)
    print("ZEIBAEL_PUBLIC_ASR_STATUS=" + result["status"])
    print("ZEIBAEL_PUBLIC_TRANSCRIPT_JSON=" + compact_public_transcript(result))
    if result["status"] == "asr_unavailable":
        print("ZEIBAEL_PUBLIC_ASR_DIAG stage=%s type=%s http=%s" %
              (result["failure_stage"], result["failure_type"], result["http_status"]))
        print("ZEIBAEL_PUBLIC_ASR_SAFE_DETAIL=" + result["failure_message"])
        print("ZEIBAEL_PUBLIC_ASR_SAFE_STACK=" + ",".join(result["failure_stack"]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
