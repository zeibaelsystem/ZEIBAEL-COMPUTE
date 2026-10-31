#!/usr/bin/env bash
set -euo pipefail
# Ubuntu GitHub-hosted runner only; approved public FFmpeg packages.
if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; then
  ffmpeg -version | head -1
  exit 0
fi
sudo apt-get update -qq
sudo apt-get install -y -qq ffmpeg
command -v ffmpeg
command -v ffprobe
