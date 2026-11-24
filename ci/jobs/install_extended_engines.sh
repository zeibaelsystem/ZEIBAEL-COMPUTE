#!/usr/bin/env bash
set -euo pipefail
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || exit 2
case "${1:-}" in
  openfoam) packages=(openfoam) ;;
  tesseract) packages=(tesseract-ocr tesseract-ocr-eng fonts-dejavu-core imagemagick) ;;
  gmsh) packages=(gmsh) ;;
  lammps) packages=(lammps) ;;
  *) echo "Unapproved engine package" >&2; exit 2 ;;
esac
sudo apt-get update -qq
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends "${packages[@]}"
