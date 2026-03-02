#!/usr/bin/env bash
set -euo pipefail

DEFAULT_APP_DIR="/home/arcade/Lightgun_Arcade_app"
if [[ -d "$DEFAULT_APP_DIR" ]]; then
  APP_DIR="$DEFAULT_APP_DIR"
else
  APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

TOOLS_DIR="$APP_DIR/tools/sinden"
mkdir -p "$TOOLS_DIR"

if ! command -v curl >/dev/null 2>&1; then
  echo "[support] curl missing. Installing..."
  sudo apt-get update -y
  sudo apt-get install -y curl
fi

SINDEN_URL="https://www.sindenlightgun.com/software/SindenLightgunSoftwareReleaseV2.08b.zip"
SINDEN_ZIP="$TOOLS_DIR/SindenLightgunSoftwareReleaseV2.08b.zip"

echo "[support] downloading official Sinden package"
curl -fL "$SINDEN_URL" -o "$SINDEN_ZIP"

if command -v unzip >/dev/null 2>&1; then
  echo "[support] extracting package to $TOOLS_DIR/release_v2.08b"
  mkdir -p "$TOOLS_DIR/release_v2.08b"
  unzip -o "$SINDEN_ZIP" -d "$TOOLS_DIR/release_v2.08b" >/dev/null
else
  echo "[support] unzip not installed; package kept as zip only."
fi

echo "[support] done"
echo "[support] package: $SINDEN_ZIP"
