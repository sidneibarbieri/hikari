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
grep -q "data-live-timeline-legend" "$page" \
  || { echo "FAIL: live board missing timeline legend mount point"; exit 1; }
echo "PASS: live board projection page rendered"

script=$(curl -sS "$CTFD_URL/plugins/hikari_plugin/assets/live.js?v=20260513c")
grep -q "function legendRow" <<<"$script" \
  || { echo "FAIL: live board script missing timeline legend renderer"; exit 1; }
grep -q "function renderYAxis" <<<"$script" \
  || { echo "FAIL: live board script missing score axis renderer"; exit 1; }
if grep -q "teamName" <<<"$script"; then
  echo "FAIL: live board script contains stale teamName reference"
  exit 1
fi
echo "PASS: live board script includes legend renderer and axis labels"

style=$(curl -sS "$CTFD_URL/plugins/hikari_plugin/assets/live.css?v=20260513c")
grep -q "live-grid--lower" <<<"$style" \
  || { echo "FAIL: live board style missing lower grid rules"; exit 1; }
grep -q "height: clamp(22rem, 38vw, 30rem)" <<<"$style" \
  || { echo "FAIL: live timeline chart is not sized as the primary lower panel"; exit 1; }
echo "PASS: live board style gives the timeline enough space"

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
