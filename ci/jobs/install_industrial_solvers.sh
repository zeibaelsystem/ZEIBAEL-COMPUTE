#!/usr/bin/env bash
# Install only reviewed open-source Ubuntu repository packages for a public CI fixture.
set -euo pipefail
if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "ZEIBAEL_INTERNAL: industrial solver install reviewed only for Linux x64" >&2
  exit 2
fi
case "${1:-}" in
  ngspice|calculix-ccx) PACKAGE="$1" ;;
  *) echo "ZEIBAEL_INTERNAL: solver package not allowlisted" >&2; exit 2 ;;
esac
if ! dpkg-query -W -f='${Status}' "$PACKAGE" 2>/dev/null | grep -q 'install ok installed'; then
  sudo apt-get update -qq
  sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends "$PACKAGE"
fi
if [[ "$PACKAGE" == "ngspice" ]]; then
  command -v ngspice
else
  command -v ccx
fi
echo "ZEIBAEL_PUBLIC_ENGINE_PACKAGE_OK $PACKAGE"
