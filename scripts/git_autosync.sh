#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$APP_DIR/.env"
VERSION_FILE="$APP_DIR/VERSION"
BRANCH="${1:-main}"
REASON="${2:-app-change}"

if [[ ! -f "$ENV_FILE" ]]; then
  exit 0
fi

if ! command -v git >/dev/null 2>&1; then
  exit 0
fi

if ! git -C "$APP_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

set +u
source "$ENV_FILE"
set -u

if [[ -z "${GITHUB_TOKEN:-}" || -z "${GITHUB_REPO:-}" ]]; then
  exit 0
fi

cd "$APP_DIR"
if [[ -z "$(git status --porcelain)" ]]; then
  exit 0
fi

current_version="0.1.0+0"
if [[ -f "$VERSION_FILE" ]]; then
  current_version="$(tr -d '[:space:]' < "$VERSION_FILE")"
fi

base="${current_version%%+*}"
build="${current_version##*+}"
if [[ "$build" == "$current_version" || ! "$build" =~ ^[0-9]+$ ]]; then
  build=0
fi
next_build=$((build + 1))
next_version="${base}+${next_build}"
printf "%s\n" "$next_version" > "$VERSION_FILE"

git add -A
if [[ -z "$(git status --porcelain)" ]]; then
  exit 0
fi

git config user.name "${GIT_USER_NAME:-Lightgun Auto Sync}"
git config user.email "${GIT_USER_EMAIL:-lightgun@local}"
git commit -m "auto: ${REASON} | v${next_version} | $(date -Iseconds)" >/dev/null 2>&1 || true

remote_url="https://${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git"
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$remote_url"
else
  git remote add origin "$remote_url"
fi

git push origin "$BRANCH" >/dev/null 2>&1 || true
