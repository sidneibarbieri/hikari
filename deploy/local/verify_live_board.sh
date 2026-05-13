#!/usr/bin/env bash
# Validates the Hikari live board beyond page availability:
# the page must render the projection surface and the JSON feed must expose
# current standings, recent solves, and timeline data from the CTFd database.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}

page=$(mktemp)
data=$(mktemp)
trap 'rm -f "$page" "$data"' EXIT

code=$(curl -sSL -o "$page" -w '%{http_code}' "$CTFD_URL/hikari/live")
[[ "$code" == "200" ]] || { echo "FAIL: /hikari/live returned $code"; exit 1; }
grep -q "Competição em tempo real" "$page" \
  || { echo "FAIL: live board missing header"; exit 1; }
grep -q "data-live-board" "$page" \
  || { echo "FAIL: live board missing JS mount point"; exit 1; }
grep -q "/plugins/hikari_plugin/assets/live.js" "$page" \
  || { echo "FAIL: live board missing polling script"; exit 1; }
echo "PASS: live board projection page rendered"

code=$(curl -sS -o "$data" -w '%{http_code}' "$CTFD_URL/hikari/live/data")
[[ "$code" == "200" ]] || { echo "FAIL: /hikari/live/data returned $code"; exit 1; }

jq -e '.generated_at and (.total_solves | type == "number")' "$data" >/dev/null \
  || { echo "FAIL: live data missing generated_at or total_solves"; exit 1; }
jq -e '.team_standings | length > 0' "$data" >/dev/null \
  || { echo "FAIL: live data has no team standings"; exit 1; }
jq -e '.individual_standings | length > 0' "$data" >/dev/null \
  || { echo "FAIL: live data has no individual standings"; exit 1; }
jq -e '.recent_solves | length > 0' "$data" >/dev/null \
  || { echo "FAIL: live data has no recent solves"; exit 1; }
jq -e '.timeline | length > 0' "$data" >/dev/null \
  || { echo "FAIL: live data has no timeline points"; exit 1; }

top_team=$(jq -r '.team_standings[0].name' "$data")
top_score=$(jq -r '.team_standings[0].score' "$data")
echo "PASS: live board data feed exposes standings, solves, and timeline"
echo "  top_team=$top_team score=$top_score"
