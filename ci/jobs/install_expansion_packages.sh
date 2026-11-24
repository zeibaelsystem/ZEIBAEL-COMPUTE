#!/usr/bin/env bash
set -euo pipefail
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || exit 2
case "${1:-}" in
  libreoffice) packages=(libreoffice-writer) ;;
  pandoc) packages=(pandoc) ;;
  tesseract_multilingual) packages=(tesseract-ocr tesseract-ocr-ind fonts-dejavu-core imagemagick) ;;
  imagemagick) packages=(imagemagick) ;;
  blender) packages=(blender) ;;
  gdal) packages=(gdal-bin) ;;
  ocrmypdf) packages=(tesseract-ocr tesseract-ocr-eng ghostscript fonts-dejavu-core) ;;
  freecad) packages=(libgl1 libegl1 libxkbcommon0 libxcb-cursor0 libxrender1) ;;
  openseespy) packages=(libblas3 liblapack3 libgfortran5) ;;
  paddleocr) packages=(fonts-dejavu-core libgl1 libglib2.0-0) ;;
  silero_vad|whisperx) packages=(espeak-ng ffmpeg) ;;
  *) echo "Unapproved package ID" >&2; exit 2 ;;
esac
sudo apt-get update -qq
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends "${packages[@]}"
