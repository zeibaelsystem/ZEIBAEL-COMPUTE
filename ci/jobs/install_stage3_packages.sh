#!/usr/bin/env bash
set -euo pipefail
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || exit 2
case "${1:-}" in
  mpi4py) packages=(libopenmpi-dev openmpi-bin) ;;
  *) exit 2 ;;
esac
sudo apt-get update -qq
sudo apt-get install -y -qq --no-install-recommends "${packages[@]}"
