#!/usr/bin/env bash
set -euo pipefail
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || exit 2
case "${1:-}" in
  mpi4py) packages=(libopenmpi-dev openmpi-bin) ;;
  nats) packages=(nats-server) ;;
  gstreamer) packages=(gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good) ;;
  mediainfo) packages=(mediainfo) ;;
  sundials) packages=(libsundials-dev) ;;
  petsc) packages=(libpetsc-real-dev pkg-config libopenmpi-dev) ;;
  gromacs) packages=(gromacs) ;;
  cp2k) packages=(cp2k cp2k-data) ;;
  precice) packages=(libeigen3-dev) ;;
  *) exit 2 ;;
esac
sudo apt-get update -qq
sudo apt-get install -y -qq --no-install-recommends "${packages[@]}"
if [[ "${1:-}" == precice ]]; then
  tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
  curl --fail --silent --show-error --location --max-time 60 'https://github.com/precice/precice/releases/download/v3.3.0/libprecice3_3.3.0_noble.deb' -o "$tmp/precice.deb"
  echo "50ad52afd3d14f5d08ab2761479a7e6829918a79debcaccddb8555676dc0d9e3  $tmp/precice.deb" | sha256sum -c -
  sudo apt-get install -y -qq --no-install-recommends "$tmp/precice.deb"
fi
