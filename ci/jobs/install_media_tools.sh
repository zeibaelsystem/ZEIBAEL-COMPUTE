#!/usr/bin/env bash
set -euo pipefail
# GitHub-hosted Ubuntu runner: approved public utilities, never provider credentials.
missing=()
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  missing+=(ffmpeg)
fi
if ! command -v tesseract >/dev/null; then
  missing+=(tesseract-ocr tesseract-ocr-eng tesseract-ocr-ind)
elif ! tesseract --list-langs 2>/dev/null | grep -qx ind; then
  missing+=(tesseract-ocr-ind)
fi
if ((${#missing[@]})); then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${missing[@]}"
fi
command -v ffmpeg
command -v ffprobe
command -v tesseract
tesseract --list-langs 2>/dev/null | grep -qx ind
