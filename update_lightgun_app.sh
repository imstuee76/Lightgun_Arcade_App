#!/usr/bin/env bash
set -euo pipefail

DEFAULT_APP_DIR="/home/arcade/Lightgun_Arcade_app"
if [[ -d "$DEFAULT_APP_DIR" ]]; then
  APP_DIR="$DEFAULT_APP_DIR"
else
  APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

DATA_DIR="$APP_DIR/data"
UPDATER_LOG_DIR="$DATA_DIR/logs/updater"
mkdir -p "$UPDATER_LOG_DIR"
LOG_FILE="$UPDATER_LOG_DIR/updater_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[updater] $(date -Iseconds) starting"
echo "[updater] app dir: $APP_DIR"

cd "$APP_DIR"
mkdir -p data/logs/app data/logs/updater data/db data/exports data/cache

ENV_BACKUP=""
if [[ -f ".env" ]]; then
  ENV_BACKUP="$(mktemp)"
  cp ".env" "$ENV_BACKUP"
  echo "[updater] .env backed up"
fi

if [[ -d ".git" ]]; then
  echo "[updater] hard resetting to origin/main"
  git fetch origin main || git fetch --all
  git reset --hard origin/main
else
  echo "[updater] warning: no git repository in $APP_DIR"
fi

if [[ -n "$ENV_BACKUP" && -f "$ENV_BACKUP" ]]; then
  cp "$ENV_BACKUP" ".env"
  rm -f "$ENV_BACKUP"
  echo "[updater] .env restored"
fi

chmod +x "$APP_DIR"/run_app.sh "$APP_DIR"/update_lightgun_app.sh "$APP_DIR"/scripts/*.sh || true

echo "[updater] checking dependencies"
bash "$APP_DIR/scripts/install_dependencies.sh"

echo "[updater] creating desktop shortcuts"
bash "$APP_DIR/scripts/create_desktop_shortcuts.sh"

echo "[updater] launch app"
bash "$APP_DIR/run_app.sh"
