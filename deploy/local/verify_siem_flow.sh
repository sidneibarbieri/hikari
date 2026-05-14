#!/usr/bin/env bash
# Exercises the competitor SIEM path through the authenticated Hikari gateway.
# This proves that a player can reach Kibana through CTFd and that a query
# request is attributed to the player's user_id in the activity log.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
COMPOSE_FILE=${COMPOSE_FILE:-$(cd "$(dirname "$0")" && pwd)/docker-compose.yml}

stamp=$(date +%s)
PLAYER_NAME="siem_${stamp}"
PLAYER_EMAIL="siem_${stamp}@hikari.local"
PLAYER_PASSWORD="siem-pw-${stamp}"

cookie_jar=$(mktemp)
trap 'rm -f "$cookie_jar" /tmp/hikari-siem-*.html /tmp/hikari-siem-*json' EXIT

extract_nonce() {
  grep -oE 'name="nonce"[^>]*value="[^"]+"' "$1" \
    | head -1 | sed -E 's/.*value="([^"]+)".*/\1/'
}

db_value() {
  local query=$1
  docker-compose -f "$COMPOSE_FILE" exec -T db \
    mariadb -uctfd -pctfd ctfd -N -B -e "$query"
}

echo "== register and login competitor =="
page=/tmp/hikari-siem-register.html
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$page" "$CTFD_URL/register"
nonce=$(extract_nonce "$page")
[[ -n "$nonce" ]] || { echo "no nonce on /register"; exit 1; }

code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/register" \
  --data-urlencode "name=$PLAYER_NAME" \
  --data-urlencode "email=$PLAYER_EMAIL" \
  --data-urlencode "password=$PLAYER_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "register returned $code"; exit 1; }

player_id=$(db_value "SELECT id FROM users WHERE email='$PLAYER_EMAIL';" | tr -d '[:space:]')
[[ -n "$player_id" ]] || { echo "user not found after register"; exit 1; }
echo "PASS: competitor persisted with id $player_id"

echo "== open Kibana through Hikari gateway =="
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o /tmp/hikari-siem-entry.html -w '%{http_code}' "$CTFD_URL/hikari/siem")
[[ "$code" == "200" ]] || { echo "SIEM entrypoint returned $code"; cat /tmp/hikari-siem-entry.html; exit 1; }
grep -q "Operação SIEM" /tmp/hikari-siem-entry.html \
  || { echo "SIEM entrypoint missing Hikari SIEM surface"; exit 1; }
grep -q "Dashboard Kibana" /tmp/hikari-siem-entry.html \
  || { echo "SIEM entrypoint missing dashboard link"; exit 1; }
grep -q "Abrir Discover" /tmp/hikari-siem-entry.html \
  || { echo "SIEM entrypoint missing Discover link"; exit 1; }
grep -q "Distribuição de severidade" /tmp/hikari-siem-entry.html \
  || { echo "SIEM entrypoint missing severity distribution"; exit 1; }
echo "PASS: SIEM entrypoint renders the Hikari SIEM surface"

status_body=/tmp/hikari-siem-status.json
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o "$status_body" -w '%{http_code}' "$CTFD_URL/hikari/kibana/api/status")
[[ "$code" == "200" ]] || { echo "gateway status returned $code"; cat "$status_body"; exit 1; }
jq -e '.status.overall.level == "available"' "$status_body" >/dev/null \
  || { echo "Kibana status is not available"; cat "$status_body"; exit 1; }
echo "PASS: Kibana status is available through the authenticated gateway"

echo "== submit a SIEM query through Kibana =="
query_body='{"query":{"match_all":{}},"size":1}'
search_body=/tmp/hikari-siem-search.json
code=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o "$search_body" -w '%{http_code}' \
  -H "Content-Type: application/json" \
  -H "kbn-xsrf: hikari" \
  -X POST "$CTFD_URL/hikari/kibana/api/console/proxy?path=/competition1/_search&method=GET" \
  -d "$query_body")
[[ "$code" == "200" ]] || { echo "console proxy returned $code"; cat "$search_body"; exit 1; }
jq -e '.hits.total.value >= 0' "$search_body" >/dev/null \
  || { echo "search response did not contain hits"; cat "$search_body"; exit 1; }
echo "PASS: Kibana query returned an Elasticsearch search response"

rows=$(db_value "SELECT COUNT(*) FROM hikari_activity WHERE actor_id=$player_id AND event_type='kibana.query';" | tr -d '[:space:]')
[[ "$rows" -ge 1 ]] || { echo "no kibana.query activity found for user $player_id"; exit 1; }
echo "PASS: kibana.query activity captured for user_id=$player_id"

payload_match=$(db_value "SELECT COUNT(*) FROM hikari_activity WHERE actor_id=$player_id AND event_type='kibana.query' AND JSON_EXTRACT(payload, '$.request_body') LIKE '%match_all%';" | tr -d '[:space:]')
[[ "$payload_match" -ge 1 ]] || { echo "kibana.query payload did not preserve the query body"; exit 1; }
echo "PASS: query body preserved for scientific analysis"

chrome_rows_before=$(db_value "SELECT COUNT(*) FROM hikari_activity WHERE actor_id=$player_id AND event_type='kibana.query' AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.path'))='api/content_management/rpc/search';" | tr -d '[:space:]')
curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o /tmp/hikari-siem-content-search.json -w '%{http_code}' \
  -H "Content-Type: application/json" \
  -H "kbn-xsrf: hikari" \
  -X POST "$CTFD_URL/hikari/kibana/api/content_management/rpc/search" \
  -d '{"query":"","contentTypes":["dashboard"]}' >/tmp/hikari-siem-content-search.status
chrome_rows_after=$(db_value "SELECT COUNT(*) FROM hikari_activity WHERE actor_id=$player_id AND event_type='kibana.query' AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.path'))='api/content_management/rpc/search';" | tr -d '[:space:]')
[[ "$chrome_rows_after" == "$chrome_rows_before" ]] \
  || { echo "Kibana content search was recorded as a hunting query"; exit 1; }
echo "PASS: Kibana chrome content search is not recorded as a hunting query"

echo
echo "SIEM gateway flow verified."
