#!/bin/bash
# W杯2026 スコア自動更新 → 変更があれば本番(GitHub Pages)へ自動push
# cron例: */30 * * * *  （30分ごと）
set -e
REPO="/Users/kenta.nakahira/worldcup2026-app"
cd "$REPO"

# 最新スコアを取得して results.json を更新
python3 scripts/update_results.py

# 変更がなければ何もしない
if git diff --quiet -- results.json; then
  echo "$(date '+%F %T') no change"
  exit 0
fi

git add results.json
git commit -q -m "auto: スコア自動更新 $(date '+%Y-%m-%d %H:%M')

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push -q origin main
echo "$(date '+%F %T') pushed"
