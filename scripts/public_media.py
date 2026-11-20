#!/usr/bin/env python3
"""Public video/post evidence on a standard GitHub runner; NO login/cookies.

Never send private links or tokens to this public workflow. A failed fetch is
not evidence of a video claim; output is bounded multimodal evidence.
"""
import base64
import json
import os
import re
import resource
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from scripts.public_media_input import identify_public_media, parse_media_window, validate_public_media_url
    from scripts.public_threads_media import fetch_threads_media
except ModuleNotFoundError:
    from public_media_input import identify_public_media, parse_media_window, validate_public_media_url
    from public_threads_media import fetch_threads_media

MAX_MEDIA_BYTES = 32_000_000
MAX_EVIDENCE_BYTES = 3_000_000
MEDIA_SUFFIXES = {".mp4", ".webm", ".m4v", ".jpg", ".jpeg", ".png", ".webp"}

def find_approved_media(root):
    """Prefer an actual downloaded video, and reject symlinks and oversized files."""
    files = []
    for p in root.rglob("*"):
        if p.is_symlink() or not p.is_file() or p.suffix.lower() not in MEDIA_SUFFIXES:
            continue
        if not 100 <= p.stat().st_size <= MAX_MEDIA_BYTES:
            continue
        files.append(p)
    files.sort(key=lambda p: (p.suffix.lower() not in {".mp4", ".m4v", ".webm"}, str(p)))
    return files[0] if files else None

def limited_command(argv, timeout):
    """Subprocess may not inherit token-bearing environment; never log CDN URLs."""
    def cap_file():
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_MEDIA_BYTES, MAX_MEDIA_BYTES))
    env = {k: v for k, v in os.environ.items()
           if k in {"PATH", "HOME", "LANG", "TMPDIR", "TMP", "TEMP", "CI"}}
    try:
        p = subprocess.run(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=timeout, check=False, env=env, preexec_fn=cap_file)
        return p.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False

def media_shortcode(url):
    """Clean canonical public post ID for matching media evidence to request."""
    return identify_public_media(url)[1]


def vision_preview_base64(frame):
    """Generate a bounded JPEG thumb for direct model byte input from public media.

    Image is a thumbnail only; original full-resolution frames remain artifacts.
    """
    if (not frame.is_file() or frame.is_symlink() or frame.suffix.lower() != ".jpg"
            or frame.stat().st_size > MAX_MEDIA_BYTES):
        raise ValueError("Expected public JPEG frame")
    with tempfile.TemporaryDirectory(prefix="zeibael-public-frame-") as folder:
        dest = Path(folder) / "preview.jpg"
        command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                   "-y", "-i", str(frame), "-frames:v", "1",
                   "-vf", "scale='min(120,iw)':-2", "-q:v", "24", str(dest)]
        if not limited_command(command, 20) or not dest.is_file():
            raise ValueError("JPEG thumbnail conversion failed")
        raw = dest.read_bytes()
    if not 400 <= len(raw) <= 3600 or not (
            raw.startswith(b"\xff\xd8\xff") and raw.endswith(b"\xff\xd9")):
        raise ValueError("JPEG thumbnail bytes failed size/signature checks")
    return base64.b64encode(raw).decode("ascii")


def capture(argv, timeout=25):
    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                       timeout=timeout, check=True)
    return p.stdout

def make_evidence(source, output):
    """Produce full-window bounded evidence, keeping the original entry point."""
    try:
        from scripts.public_video_intelligence import make_evidence_v2
    except ModuleNotFoundError:
        from public_video_intelligence import make_evidence_v2
    return make_evidence_v2(source, output, limited_command, capture)


def public_extractor_commands(url, folder, window=None):
    platform, _, canonical = identify_public_media(url)
    if platform == "threads":
        return []
    ytdlp = [sys.executable, "-m", "yt_dlp", "--ignore-config",
             "--use-extractors", platform, "--no-playlist", "--no-progress",
             "--no-warnings", "--no-cache-dir", "--no-part", "--max-filesize", "28M",
             "--socket-timeout", "12", "--retries", "1",
             "-f", "b[height<=480][ext=mp4]/b[height<=480]/bv*[height<=480]+ba/b[ext=mp4]/best",
             "--merge-output-format", "mp4", "-o", str(folder / "source.%(ext)s")]
    if window:
        ytdlp += ["--download-sections", f"*{window[0]}-{window[1]}", "--force-keyframes-at-cuts"]
    ytdlp.append(canonical)
    commands = [("yt-dlp", ytdlp)]
    if platform == "tiktok" or (platform == "instagram" and not window):
        gal = [sys.executable, "-m", "gallery_dl", "--config-ignore",
               "--no-input", "--no-part", "--quiet", "--retries", "1",
               "--http-timeout", "12", "--filesize-max", "28M",
               "--range", "1", "-D", str(folder), canonical]
        commands.append(("gallery-dl", gal))
    return commands


def fetch_public_media(url, folder, window=None):
    """Only reviewed, platform-specific public acquisition routes."""
    platform, _, canonical = identify_public_media(url)
    if platform == "threads":
        return "threads-open-graph" if fetch_threads_media(canonical, folder) else None
    for name, command in public_extractor_commands(canonical, folder, window):
        # Keep partial results from one extractor out of the next attempt.
        # The current routes write into the job's own temporary tree.
        for child in folder.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink()
        if limited_command(command, 80) and find_approved_media(folder):
            return name
    return None


def vision_frame_bundle(folder, records, media_id, platform):
    """Small, timestamped, model-ready JPEGs; full frames remain artifacts."""
    if not records:
        return {"media_id": media_id, "platform": platform, "frames": []}
    count = min(6, len(records))
    indexes = [round(i * (len(records) - 1) / max(1, count - 1)) for i in range(count)]
    frames = []
    for i in indexes:
        row = records[i]
        name = row["file"]
        if not re.fullmatch(r"frame_[0-9]{2}\.jpg", name):
            continue
        try:
            encoded = vision_preview_base64(folder / name)
        except (OSError, ValueError, subprocess.SubprocessError):
            continue
        frames.append({"frame": name, "seconds": row["seconds"], "mime_type": "image/jpeg",
                       "jpeg_base64": encoded})
    return {"media_id": media_id, "platform": platform, "frames": frames}


def offset_video_records(report, window):
    start, end = window
    report["requested_window"] = {"start": start, "end": end}
    report["timestamp_origin_seconds"] = start
    report["media_hash_scope"] = "processed_window_file"
    for row in report["frame_records"] + report["ocr"]:
        row["seconds"] = round(start + row["seconds"], 3)
    for row in report["scenes"]:
        for key in ("start", "end"):
            row[key] = round(start + row[key], 3)
    report["sampled_seconds"] = [round(start + a, 3) for a in report["sampled_seconds"]]


def needs_local_window_trim(extractor, window):
    return bool(window and extractor in {"threads-open-graph", "gallery-dl"})


def main():
    url = validate_public_media_url(os.environ.get("ZEIBAEL_MEDIA_URL", ""))
    platform, media_id, _ = identify_public_media(url)
    window = parse_media_window(os.environ.get("ZEIBAEL_MEDIA_WINDOW", ""))
    destination = Path(os.environ["ZEIBAEL_OUTPUT_DIR"]) / "files"
    if destination.exists():
        raise ValueError("Output already exists")
    destination.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="zeibael-public-media-") as tmp:
        source_dir = Path(tmp)
        extractor = fetch_public_media(url, source_dir, window)
        media = find_approved_media(source_dir)
        if not extractor or not media:
            raise RuntimeError("SOURCE_MEDIA_UNAVAILABLE: public extractors returned no usable media")
        if needs_local_window_trim(extractor, window):
            segment = source_dir / "segment.mp4"
            if not limited_command(["ffmpeg", "-nostdin", "-v", "error", "-y",
                                    "-ss", str(window[0]), "-i", str(media),
                                    "-t", str(window[1]-window[0]), "-c:v", "libx264",
                                    "-preset", "veryfast", "-c:a", "aac", str(segment)], 90):
                raise RuntimeError("FOCUS_WINDOW_UNAVAILABLE")
            media = segment
        result = make_evidence(media, destination)
        if window:
            if result["kind"] != "video" or not 0 < result["duration_seconds"] <= window[1] - window[0] + 2:
                raise RuntimeError("FOCUS_WINDOW_NOT_VERIFIED")
            offset_video_records(result, window)
    result.update({"schema": 2, "source": "public_" + platform, "platform": platform, "media_id": media_id,
                   "extractor": extractor,
                   "status": "media_decoded_not_claim_verified"})
    (destination / "media-result.json").write_text(json.dumps(result, indent=2))
    print("ZEIBAEL_PUBLIC_MEDIA_OK kind=%s frames=%d speech=%s" %
          (result["kind"], len(result["frames"]), bool(result["speech"])))
    # Public-only, short, log-delivered model-usable JPEG bytes; no signed URLs.
    if result["frames"]:
        try:
            preview = vision_preview_base64(destination / result["frames"][0])
            visual = {"media_id": media_shortcode(url), "frame": result["frames"][0],
                      "mime_type": "image/jpeg", "jpeg_base64": preview}
            print("ZEIBAEL_PUBLIC_VISION_PREVIEW=" +
                  json.dumps(visual, separators=(",", ":")))
        except (OSError, ValueError, subprocess.SubprocessError):
            print("ZEIBAEL_PUBLIC_VISION_PREVIEW_UNAVAILABLE")
        bundle = vision_frame_bundle(destination, result["frame_records"], media_id, platform)
        (destination / "vision-frames.json").write_text(json.dumps(bundle, separators=(",", ":")))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as ex:
        # Never print potentially signed remote media URLs or secret-bearing errors.
        print("ZEIBAEL_PUBLIC_MEDIA_FAILED type=" + type(ex).__name__)
        raise SystemExit(2)
