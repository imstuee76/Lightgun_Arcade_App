#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

require_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_apt_pkg() {
  local pkg="$1"
  if dpkg -s "$pkg" >/dev/null 2>&1; then
    echo "[deps] apt package already installed: $pkg"
    return
  fi
  echo "[deps] installing apt package: $pkg"
  sudo apt-get install -y "$pkg"
}

if require_cmd apt-get; then
  echo "[deps] refreshing apt index"
  sudo apt-get update -y
  for pkg in git python3 python3-pip python3-tk fceux x11-xserver-utils; do
    install_apt_pkg "$pkg"
  done
fi

echo "[deps] installing python requirements"
if python3 -m pip install --break-system-packages -r "$APP_DIR/requirements.txt"; then
  true
else
  python3 -m pip install -r "$APP_DIR/requirements.txt"
fi

echo "[deps] dependency check complete"
