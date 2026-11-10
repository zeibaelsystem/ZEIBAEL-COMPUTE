#!/usr/bin/env python3
"""Join bounded public video, OCR, scenes, and timestamped ASR into evidence."""
import json
import math
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

CHUNK_SECONDS = 40
MAX_FULL_SECONDS = 300


def transcribe_full(model, audio, seconds, read_pcm, transcribe, serialize):
    """Decode at most 40 seconds per CPU Whisper call; preserve source offsets."""
    if not audio.is_file() or audio.is_symlink() or audio.stat().st_size > 12_000_000:
        raise ValueError("Invalid public compressed audio")
    duration = float(seconds)
    if not math.isfinite(duration) or not 0 < duration <= MAX_FULL_SECONDS:
        raise ValueError("Unsafe full-audio coverage")
    rows, infos, fallbacks = [], [], []
    with tempfile.TemporaryDirectory(prefix="zeibael-asr-") as temp:
        for begin in range(0, math.ceil(duration), CHUNK_SECONDS):
            length = min(CHUNK_SECONDS, duration - begin)
            if length <= 0:
                break
            wav = Path(temp) / ("chunk_%03d.wav" % begin)
            cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                   "-ss", str(begin), "-i", str(audio), "-t", str(length),
                   "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)]
            p = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=50, check=False)
            if p.returncode or not wav.is_file() or not 1000 < wav.stat().st_size < 1_800_000:
                raise RuntimeError("Local audio chunk decode failed")
            samples = read_pcm(wav)
            segments, info, fallback = transcribe(model, samples)
            # Faster Whisper evaluates lazily; consume while the chunk still exists.
            for seg in segments:
                rows.append(SimpleNamespace(start=float(seg.start) + begin,
                                            end=float(seg.end) + begin,
                                            text=str(seg.text)))
            infos.append(info)
            fallbacks.append(fallback)
    meta = infos[0] if infos else SimpleNamespace(language=None, language_probability=0)
    result = serialize(rows, meta)
    result["audio_coverage_seconds"] = round(duration, 3)
    result["chunks_processed"] = len(infos)
    result["no_vad_fallback_used"] = any(fallbacks)
    return result


def write_timeline(root, transcript):
    """Evidence-only timeline; no inference that visual frames prove video claims."""
    media_path = root / "media-result.json"
    if not media_path.is_file() or media_path.is_symlink():
        return
    media = json.loads(media_path.read_text(encoding="utf-8"))
    ocr = {item["frame"]: item for item in media.get("ocr", [])}
    frames = []
    for item in media.get("frame_records", []):
        frames.append({"frame": item["file"], "seconds": item["seconds"],
                       "ocr": ocr.get(item["file"], {"text": "", "status": "unavailable"})})
    result = {
        "schema": 1,
        "source": media.get("source"),
        "media_sha256": media.get("media_sha256"),
        "duration_seconds": media.get("duration_seconds"),
        "scene_detection": media.get("scene_detection"),
        "scenes": media.get("scenes", []),
        "frames": frames,
        "speech": transcript.get("segments", []),
        "speech_status": transcript.get("status", "asr_unavailable"),
        "coverage": media.get("coverage", {}),
        "visual_inference": "not_performed_in_runner",
        "claim_verification": "not_verified",
    }
    (root / "timeline.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
