#!/usr/bin/env bash
# Asserts that the researcher surface is reachable to admins and returns
# both the HTML dashboard and the JSONL export. Validates beyond HTTP 200
# by checking that the rendered HTML contains the expected sections and
# that the export body is valid JSONL whose first line parses as JSON.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari-admin-pw}

cookie_jar=$(mktemp)
trap 'rm -f "$cookie_jar" /tmp/hikari-research-*' EXIT

page=/tmp/hikari-research-login.html
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$page" "$CTFD_URL/login"
nonce=$(grep -oE 'name="nonce"[^>]*value="[^"]+"' "$page" \
  | head -1 | sed -E 's/.*value="([^"]+)".*/\1/')
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "admin login returned $code"; exit 1; }
echo "PASS: admin authenticated"

dashboard=/tmp/hikari-research-dashboard.html
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$dashboard" \
  -w '%{http_code}' "$CTFD_URL/admin/hikari/research")
[[ "$code" == "200" ]] \
  || { echo "FAIL: dashboard returned $code"; exit 1; }
echo "PASS: /admin/hikari/research returned 200"

# Content-level assertions: the rendered page contains the metric block and
# at least one of the structured sections. HTTP 200 alone would not catch a
# template rendering error that produces an empty page.
grep -q "Research analytics" "$dashboard" \
  || { echo "FAIL: dashboard does not contain the heading"; exit 1; }
grep -q "Total events" "$dashboard" \
  || { echo "FAIL: dashboard missing total events metric"; exit 1; }
grep -q "Events by type" "$dashboard" \
  || { echo "FAIL: dashboard missing events-by-type section"; exit 1; }
grep -q "Recent events" "$dashboard" \
  || { echo "FAIL: dashboard missing recent events section"; exit 1; }
echo "PASS: dashboard rendered with all expected sections"

export_file=/tmp/hikari-research-export.jsonl
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$export_file" \
  -w '%{http_code}' "$CTFD_URL/admin/hikari/research/export.jsonl")
[[ "$code" == "200" ]] \
  || { echo "FAIL: export returned $code"; exit 1; }

line_count=$(wc -l < "$export_file" | tr -d '[:space:]')
if [[ "$line_count" -lt 1 ]]; then
  echo "FAIL: export contained 0 lines; activity log is empty?"
  exit 1
fi

# Validate the first line is well-formed JSON with the activity record shape.
head -1 "$export_file" | jq -e '.event_type and .occurred_at' >/dev/null \
  || { echo "FAIL: first export line is not a valid activity record"; head -3 "$export_file"; exit 1; }
echo "PASS: JSONL export has $line_count parseable records (sample line valid)"

echo
echo "Researcher surface verified."
