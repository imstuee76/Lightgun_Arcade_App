#!/usr/bin/env bash
set -euo pipefail

DEFAULT_APP_DIR="/home/arcade/Lightgun_Arcade_app"
if [[ -d "$DEFAULT_APP_DIR" ]]; then
  APP_DIR="$DEFAULT_APP_DIR"
else
  APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

DESKTOP_DIR="${HOME}/Desktop"
APP_DESKTOP_FILE="${HOME}/.local/share/applications/lightgun-arcade.desktop"
UPDATER_DESKTOP_FILE="${HOME}/.local/share/applications/lightgun-arcade-updater.desktop"

mkdir -p "${HOME}/.local/share/applications" "$DESKTOP_DIR"

cat > "$APP_DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Lightgun Arcade App
Comment=Launch the Lightgun Arcade App
Exec=${APP_DIR}/run_app.sh
Icon=applications-games
Terminal=true
Categories=Game;
EOF

cat > "$UPDATER_DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Lightgun Arcade Updater
Comment=Update and launch Lightgun Arcade App
Exec=${APP_DIR}/update_lightgun_app.sh
Icon=system-software-update
Terminal=true
Categories=Utility;
EOF

chmod +x "$APP_DESKTOP_FILE" "$UPDATER_DESKTOP_FILE"
cp -f "$APP_DESKTOP_FILE" "$DESKTOP_DIR/Lightgun Arcade App.desktop"
cp -f "$UPDATER_DESKTOP_FILE" "$DESKTOP_DIR/Lightgun Arcade Updater.desktop"
chmod +x "$DESKTOP_DIR/Lightgun Arcade App.desktop" "$DESKTOP_DIR/Lightgun Arcade Updater.desktop"

echo "[desktop] shortcuts created in ${DESKTOP_DIR}"
