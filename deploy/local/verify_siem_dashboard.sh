#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
COMPOSE_FILE=${COMPOSE_FILE:-"$SCRIPT_DIR/docker-compose.yml"}
CTFD_URL=${CTFD_URL:-http://localhost:8000}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari-admin-pw}

compose() {
  docker-compose -f "$COMPOSE_FILE" "$@"
}

kibana() {
  compose exec -T kibana curl -sS "$@"
}

elasticsearch() {
  compose exec -T elasticsearch curl -sS "$@"
}

extract_nonce() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" \
    | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

echo "== validate SIEM saved objects =="
dashboard=$(kibana \
  -H "kbn-xsrf: true" \
  "http://localhost:5601/hikari/kibana/api/saved_objects/dashboard/hikari-siem")
title=$(echo "$dashboard" | jq -r '.attributes.title // empty')
[[ "$title" == "HIKARI SIEM" ]] \
  || { echo "FAIL: HIKARI SIEM dashboard not found"; exit 1; }
panels=$(echo "$dashboard" | jq -r '.attributes.panelsJSON | fromjson | length')
[[ "$panels" -ge 16 ]] \
  || { echo "FAIL: dashboard has too few panels ($panels)"; exit 1; }
echo "PASS: HIKARI SIEM dashboard has $panels panels"

metric_panels=$(kibana \
  -H "kbn-xsrf: true" \
  "http://localhost:5601/hikari/kibana/api/saved_objects/_find?type=visualization&search_fields=title&per_page=100" \
  | jq -r '[.saved_objects[] | select((.attributes.visState | fromjson).type == "metric")] | length')
[[ "$metric_panels" == "0" ]] \
  || { echo "FAIL: legacy metric visualizations still present ($metric_panels)"; exit 1; }
echo "PASS: SIEM dashboard avoids unstable legacy metric panels"

data_view=$(kibana \
  -H "kbn-xsrf: true" \
  "http://localhost:5601/hikari/kibana/api/data_views/data_view/competition1")
for field in "@timestamp" "Source IP" "Destination IP" "Destination Port" "Threat Severity (custom)" "Fortinet Message (custom)"; do
  echo "$data_view" | jq -e --arg field "$field" \
    '[.data_view.fields[].name] | index($field) != null' >/dev/null \
    || { echo "FAIL: data view is missing field: $field"; exit 1; }
done
echo "PASS: SIEM data view exposes core hunting fields"

count=$(elasticsearch "http://localhost:9200/competition1/_count" | jq -r '.count')
[[ "$count" -gt 0 ]] \
  || { echo "FAIL: competition1 index has no events"; exit 1; }
echo "PASS: competition1 contains $count events"

echo "== validate authenticated dashboard route =="
cookie_jar=$(mktemp)
page=$(mktemp)
trap 'rm -f "$cookie_jar" "$page"' EXIT

curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$page" "$CTFD_URL/login"
nonce=$(extract_nonce "$page")
[[ -n "$nonce" ]] || { echo "FAIL: login nonce missing"; exit 1; }

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "FAIL: admin login returned $code"; exit 1; }

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o "$page" -w '%{http_code}' \
  "$CTFD_URL/hikari/kibana/app/dashboards")
[[ "$code" == "200" ]] \
  || { echo "FAIL: dashboard app route returned $code"; exit 1; }
grep -q "kbn-injected-metadata" "$page" \
  || { echo "FAIL: Kibana dashboard app did not render shell"; exit 1; }
echo "PASS: dashboard route is reachable through the authenticated gateway"
