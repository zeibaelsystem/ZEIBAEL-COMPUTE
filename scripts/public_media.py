#!/usr/bin/env python3
"""Public Instagram media evidence on a standard GitHub runner; NO login/cookies.

Never send private links or tokens to this public workflow. A failed fetch is
not evidence of a video claim; output only sampled frames and short speech audio.
"""
import hashlib
import json
import os
import resource
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from scripts.public_media_input import validate_public_media_url
except ModuleNotFoundError:
    from public_media_input import validate_public_media_url

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

def capture(argv, timeout=25):
    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                       timeout=timeout, check=True)
    return p.stdout

def make_evidence(source, output):
    """Make bounded, public-only artifacts suitable for vision and full-clip ASR."""
    output.mkdir(parents=True, exist_ok=True)
    info = json.loads(capture(["ffprobe", "-v", "error", "-show_format",
                               "-show_streams", "-of", "json", str(source)]))
    streams = info.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = any(s.get("codec_type") == "audio" for s in streams)
    if video is None:
        raise ValueError("Media has no visual stream")
    duration = float(info.get("format", {}).get("duration") or 0.0)
    if duration < 0 or duration > 3600:
        raise ValueError("Unsafe duration")
    is_video = source.suffix.lower() in (".mp4", ".m4v", ".webm")
    shots = [0.0] if not is_video else sorted(set([0.0, min(18.0, duration * 0.35),
                                                          min(42.0, duration * 0.75)]))
    frames = []
    for idx, seconds in enumerate(shots):
        name = "frame_%02d.jpg" % idx
        dest = output / name
        args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
        if seconds:
            args += ["-ss", str(seconds)]
        args += ["-i", str(source), "-frames:v", "1",
                 "-vf", "scale='min(480,iw)':-2", "-q:v", "6", str(dest)]
        if not limited_command(args, 25) or not dest.is_file() or dest.stat().st_size < 500:
            if idx == 0:
                raise ValueError("Could not decode the first frame")
            continue
        frames.append(name)
    speech = None
    if is_video and audio:
        dest = output / "speech.wav"
        args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(source), "-vn", "-t", "55", "-ar", "16000",
                "-ac", "1", "-c:a", "pcm_s16le", str(dest)]
        if limited_command(args, 25) and dest.is_file() and dest.stat().st_size > 1000:
            speech = "speech.wav"
    paths = [output / x for x in frames + ([speech] if speech else [])]
    if sum(p.stat().st_size for p in paths) > MAX_EVIDENCE_BYTES:
        raise ValueError("Evidence exceeds public artifact limit")
    return {"kind": "video" if is_video else "image",
            "frames": frames, "speech": speech,
            "sampled_seconds": [round(x, 3) for x in shots[:len(frames)]],
            "media_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "artifacts": [{"name": p.name, "size": p.stat().st_size}
                          for p in paths]}

def fetch_public_media(url, folder):
    """Two independent public extractors; no credentials, no paid access, no bypass."""
    ytdlp = [sys.executable, "-m", "yt_dlp", "--ignore-config",
             "--no-playlist", "--no-progress", "--no-warnings",
             "--no-cache-dir", "--no-part", "--max-filesize", "28M",
             "--socket-timeout", "12", "--retries", "1",
             "-f", "b[ext=mp4]/best", "-o", str(folder / "reel.%(ext)s"), url]
    if limited_command(ytdlp, 80) and find_approved_media(folder):
        return "yt-dlp"
    gal = [sys.executable, "-m", "gallery_dl", "--config-ignore",
           "--no-input", "--no-part", "--quiet", "--retries", "1",
           "--http-timeout", "12", "--filesize-max", "28M",
           "--range", "1", "-D", str(folder), url]
    if limited_command(gal, 80) and find_approved_media(folder):
        return "gallery-dl"
    return None

def main():
    url = validate_public_media_url(os.environ.get("ZEIBAEL_MEDIA_URL", ""))
    destination = Path(os.environ["ZEIBAEL_OUTPUT_DIR"]) / "files"
    if destination.exists():
        raise ValueError("Output already exists")
    destination.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="zeibael-public-media-") as tmp:
        source_dir = Path(tmp)
        extractor = fetch_public_media(url, source_dir)
        media = find_approved_media(source_dir)
        if not extractor or not media:
            raise RuntimeError("SOURCE_MEDIA_UNAVAILABLE: public extractors returned no usable media")
        result = make_evidence(media, destination)
    result.update({"schema": 1, "source": "public_instagram", "extractor": extractor,
                   "status": "media_decoded_not_claim_verified"})
    (destination / "media-result.json").write_text(json.dumps(result, indent=2))
    print("ZEIBAEL_PUBLIC_MEDIA_OK kind=%s frames=%d speech=%s" %
          (result["kind"], len(result["frames"]), bool(result["speech"])))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as ex:
        # Never print potentially signed remote media URLs or secret-bearing errors.
        print("ZEIBAEL_PUBLIC_MEDIA_FAILED type=" + type(ex).__name__)
        raise SystemExit(2)
