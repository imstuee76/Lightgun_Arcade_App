#!/usr/bin/env bash
set -euo pipefail

DEFAULT_APP_DIR="/home/arcade/Lightgun_Arcade_app"
if [[ -d "$DEFAULT_APP_DIR" ]]; then
  APP_DIR="$DEFAULT_APP_DIR"
else
  APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

DATA_DIR="$APP_DIR/data"
LOG_DIR="$DATA_DIR/logs/app"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/launcher_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[run_app] $(date -Iseconds) starting app from $APP_DIR"
cd "$APP_DIR"
python3 app.py
