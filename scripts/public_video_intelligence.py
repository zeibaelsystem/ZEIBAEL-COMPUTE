#!/usr/bin/env python3
"""Bounded public-only multimodal evidence extraction, not a claim verifier.

GitHub Actions output is public. Never feed secrets, private or authenticated
media, cookies, or signed URLs into this pipeline.
"""
import hashlib
import json
import math
import subprocess
from pathlib import Path

MAX_FRAMES = 36
MAX_FULL_ANALYSIS_SECONDS = 300.0
MAX_EVIDENCE_BYTES = 12_000_000


def select_frame_seconds(duration, scenes, limit=MAX_FRAMES, fps=30.0):
    """Cover the whole clip and avoid seeking beyond low-FPS final frames."""
    duration = max(0.0, float(duration))
    if limit < 2:
        raise ValueError("Frame limit must be at least 2")
    if not math.isfinite(float(fps)) or not 0 < float(fps) <= 240:
        raise ValueError("Invalid video frame rate")
    if duration == 0:
        return [0.0]
    last = max(0.0, duration - max(0.15, 1.2 / float(fps)))
    # Evenly spaced samples prevent a scene detector miss from omitting long spans.
    # Reserve capacity for scene cuts, even in five-minute videos.
    uniform_budget = max(2, limit - max(4, limit // 4))
    base_count = min(uniform_budget, max(2, math.ceil(duration / 5.0) + 1))
    base = [last * i / (base_count - 1) for i in range(base_count)]
    cut_points = []
    for scene in scenes:
        start, end = float(scene["start"]), float(scene["end"])
        if 0 <= start <= end <= duration + 0.5:
            cut_points.append(min(last, (start + end) / 2))
            if start > 0:
                cut_points.append(min(last, start + 0.1))
    result = sorted(set(round(v, 3) for v in base + cut_points + [0.0, last]))
    if len(result) > limit:
        # Select closest cut candidates around a uniform skeleton, without
        # sacrificing start/end coverage. Stable and deterministic.
        must = {result[0], result[-1]}
        skeleton = sorted(set(round(v, 3) for v in base))
        for target in skeleton:
            must.add(min(result, key=lambda v: (abs(v - target), v)))
        remaining = limit - len(must)
        if remaining > 0:
            candidates = [v for v in result if v not in must]
            cuts = [v for v in candidates if any(abs(v - p) < 0.02 for p in cut_points)]
            if len(cuts) > remaining:
                # Choose cuts across the whole video, not just its opening.
                indexes = [round(i * (len(cuts) - 1) / (remaining - 1))
                           for i in range(remaining)] if remaining > 1 else [len(cuts) // 2]
                chosen = [cuts[i] for i in indexes]
            else:
                chosen = (cuts + [v for v in candidates if v not in cuts])[:remaining]
            must.update(chosen)
        result = sorted(must)
    return result[:limit]


def discover_scenes(source, duration):
    """Report missing/failed detection distinctly from a true single scene."""
    try:
        from scenedetect import detect, ContentDetector
    except ImportError:
        return [], "unavailable"
    try:
        found = detect(str(source), ContentDetector(threshold=27.0), show_progress=False)
        scenes = []
        for start, end in found:
            a, b = float(start.get_seconds()), float(end.get_seconds())
            if 0 <= a < b <= duration + 0.5:
                scenes.append({"start": round(a, 3), "end": round(min(duration, b), 3)})
        return scenes, "completed"
    except (OSError, ValueError, RuntimeError, TypeError):
        return [], "failed"


def extract_ocr(frame):
    """Return status as well as text; never hide missing OCR as an empty screen."""
    try:
        p = subprocess.run(["tesseract", str(frame), "stdout", "-l", "eng+ind"],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=12, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return "", "unavailable"
    if p.returncode:
        return "", "failed"
    return p.stdout.decode("utf-8", errors="replace").strip()[:550], "completed"


def make_evidence_v2(source, output, limited_command, capture):
    """Extract scene-aware frames, OCR, and full-window compressed audio."""
    output.mkdir(parents=True, exist_ok=True)
    probe = json.loads(capture(["ffprobe", "-v", "error", "-show_format",
                                "-show_streams", "-of", "json", str(source)]))
    tracks = probe.get("streams") or []
    if not any(v.get("codec_type") == "video" for v in tracks):
        raise ValueError("Media has no visual stream")
    audio = any(v.get("codec_type") == "audio" for v in tracks)
    video_track = next(v for v in tracks if v.get("codec_type") == "video")
    rate = str(video_track.get("avg_frame_rate") or video_track.get("r_frame_rate") or "30/1")
    try:
        numerator, denominator = rate.split("/")
        fps = float(numerator) / float(denominator)
        if not math.isfinite(fps) or not 0 < fps <= 240:
            fps = 30.0
    except (ValueError, ZeroDivisionError):
        fps = 30.0
    duration = float(probe.get("format", {}).get("duration") or 0)
    if not math.isfinite(duration) or duration < 0 or duration > 3600:
        raise ValueError("Unsafe duration")
    is_video = source.suffix.lower() in (".mp4", ".m4v", ".webm")
    window = min(duration, MAX_FULL_ANALYSIS_SECONDS)
    # Container duration can exceed the visible stream (e.g. audio-only tail).
    # The stream duration is evidence; do not seek pixels after it ends.
    try:
        video_stream_end = (float(video_track.get("start_time") or 0)
                            + float(video_track.get("duration") or 0))
    except (TypeError, ValueError):
        video_stream_end = 0.0
    if not math.isfinite(video_stream_end) or video_stream_end <= 0:
        video_stream_end = duration
    visual_window = min(window, max(0, video_stream_end))
    if is_video:
        scenes, scene_status = discover_scenes(source, visual_window)
        timestamps = select_frame_seconds(visual_window, scenes, fps=fps)
    else:
        scenes, scene_status, timestamps = [], "not_video", [0.0]

    frames, frame_records, ocr_records, failures = [], [], [], []
    for idx, second in enumerate(timestamps):
        name = "frame_%02d.jpg" % idx
        dest = output / name
        attempts = [second]
        # Some MP4s have an inaccurate declared visual end or sparse keyframes.
        # Retry bounded earlier timestamps, preserving the actual requested seek.
        if idx == len(timestamps) - 1 and second > 0:
            attempts += [round(max(0.0, second - delta), 3)
                         for delta in (0.5, 1.0, 2.0, 3.5, 5.0)]
        success = False
        for seek in dict.fromkeys(attempts):
            dest.unlink(missing_ok=True)
            args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
            if seek:
                args += ["-ss", str(seek)]
            args += ["-i", str(source), "-frames:v", "1",
                     "-vf", "scale='min(480,iw)':-2", "-q:v", "7", str(dest)]
            if limited_command(args, 25) and dest.is_file() and dest.stat().st_size >= 500:
                second, success = seek, True
                break
        if not success:
            failures.append(round(second, 3))
            if idx == 0:
                raise ValueError("Could not decode the first frame")
            dest.unlink(missing_ok=True)
            continue
        frames.append(name)
        frame_records.append({"file": name, "seconds": round(second, 3)})
        text, status = extract_ocr(dest)
        ocr_records.append({"frame": name, "seconds": round(second, 3),
                            "text": text, "status": status})

    speech = None
    speech_full = None
    if is_video and audio:
        legacy = output / "speech.wav"
        short_cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                     "-i", str(source), "-vn", "-t", "55", "-ar", "16000",
                     "-ac", "1", "-c:a", "pcm_s16le", str(legacy)]
        if limited_command(short_cmd, 40) and legacy.is_file() and legacy.stat().st_size > 1000:
            speech = legacy.name
        full = output / "speech_full.opus"
        full_cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(source), "-vn", "-t", str(window), "-ar", "16000",
                    "-ac", "1", "-c:a", "libopus", "-b:a", "24k", str(full)]
        if window and limited_command(full_cmd, 65) and full.is_file() and full.stat().st_size > 1000:
            speech_full = full.name

    names = frames + ([speech] if speech else []) + ([speech_full] if speech_full else [])
    files = [output / name for name in names]
    if sum(path.stat().st_size for path in files) > MAX_EVIDENCE_BYTES:
        raise ValueError("Evidence exceeds bounded public artifact limit")
    if is_video and audio and not (speech or speech_full):
        raise ValueError("Audio extraction failed")

    coverage = {
        "video_seconds": round(duration, 3),
        "window_seconds": round(window, 3),
        "visual_stream_end_seconds": round(video_stream_end, 3),
        "visual_window_seconds": round(visual_window, 3),
        "visual_last_sample_seconds": frame_records[-1]["seconds"] if frame_records else None,
        "visual_gap_seconds": round(max(0, window - frame_records[-1]["seconds"]), 3) if frame_records else round(window, 3),
        "visual_track_shorter_than_media": video_stream_end + 0.75 < duration,
        "visual_full_window_sampled": bool(frame_records and frame_records[-1]["seconds"] >= max(0, window - max(0.75, 1.5 / fps))
                                         and video_stream_end + 0.75 >= window and not failures),
        "audio_seconds_available": round(window if speech_full else min(window, 55) if speech else 0, 3),
        "duration_limited": duration > MAX_FULL_ANALYSIS_SECONDS,
        "frames_failed": failures,
    }
    return {
        "kind": "video" if is_video else "image",
        "duration_seconds": round(duration, 3),
        "frames": frames,
        "frame_records": frame_records,
        "sampled_seconds": [r["seconds"] for r in frame_records],
        "scene_detection": scene_status,
        "scenes": scenes,
        "ocr": ocr_records,
        "speech": speech,
        "speech_full": speech_full,
        "coverage": coverage,
        "media_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "artifacts": [{"name": p.name, "size": p.stat().st_size} for p in files],
    }
