#!/usr/bin/env bash
# Build, commit and push the site from this repo; GitHub Pages serves main's root.
# Usage: ./deploy.sh ["commit message"]
# Env: FF_GAME_REPO = the game checkout build.py reads (default ~/code/faunafantasy).
# Publishing is public: run only with Mike's go-ahead.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" != "main" ]; then
  echo "on '$branch'; Pages publishes main. Switch to main first." >&2
  exit 1
fi

echo "1/3 building assets…"
python3 build.py
touch .nojekyll

echo "2/3 committing…"
git add -A
if git diff --cached --quiet; then
  echo "  nothing new to commit"
else
  git commit -m "${1:-[WEB.site] $(date +%F) site update}"
fi

echo "3/3 pushing…"
git push -u origin main
echo "done → https://faunafantasy.com/ (Pages rebuilds in a minute or two)"
