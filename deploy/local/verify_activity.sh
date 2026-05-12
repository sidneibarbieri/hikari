#!/usr/bin/env bash
# Drives a real admin login and asserts an activity record reached both the
# relational store (read via CTFd's own SQL container) and the Elasticsearch
# index 'hikari-activity'. Proves the full path: HTTP -> after_request hook
# -> DB + Kafka -> Logstash -> Elasticsearch.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
ES_URL=${ES_URL:-http://localhost:9200}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari-admin-pw}
COMPOSE_FILE=${COMPOSE_FILE:-/Users/sidneibarbieri/hikari_project/hikari/hikari-platform/deploy/local/docker-compose.yml}

cookie_jar=$(mktemp)
trap 'rm -f "$cookie_jar"' EXIT

before=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "marker timestamp: $before"

login_page=$(mktemp)
curl -sS -c "$cookie_jar" -b "$cookie_jar" -o "$login_page" "$CTFD_URL/login"
nonce=$(grep -oE 'name="nonce"[^>]*value="[^"]+"' "$login_page" \
  | head -1 | sed -E 's/.*value="([^"]+)".*/\1/')
rm -f "$login_page"
[[ -n "$nonce" ]] || { echo "no nonce on /login"; exit 1; }

status=$(curl -sS -c "$cookie_jar" -b "$cookie_jar" \
  -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$status" == "302" ]] || { echo "login returned $status (expected 302)"; exit 1; }
echo "login submitted (status 302)"

echo "checking relational store ..."
db_query='SELECT COUNT(*) FROM hikari_activity WHERE event_type='\''user.login'\'' AND occurred_at >= '\'"$before"\'';'
db_hits=$(docker-compose -f "$COMPOSE_FILE" exec -T db \
  mariadb -uctfd -pctfd ctfd -N -B -e "$db_query")
db_hits=${db_hits//[[:space:]]/}
if [[ "$db_hits" -lt 1 ]]; then
  echo "FAIL: no user.login row found in hikari_activity since $before"
  exit 1
fi
echo "PASS: $db_hits row(s) in hikari_activity for user.login since marker"

echo "polling Elasticsearch hikari-activity index ..."
deadline=$((SECONDS + 30))
es_hits=0
while (( SECONDS < deadline )); do
  resp=$(curl -sS "$ES_URL/hikari-activity/_search?q=event_type:user.login&size=1")
  es_hits=$(echo "$resp" | jq -r '.hits.total.value // 0')
  if [[ "$es_hits" -ge 1 ]]; then
    break
  fi
  sleep 2
done
if [[ "$es_hits" -lt 1 ]]; then
  echo "FAIL: hikari-activity index has no user.login document"
  curl -sS "$ES_URL/hikari-activity/_search?size=1" | jq .
  exit 1
fi
echo "PASS: hikari-activity index has $es_hits user.login document(s)"

echo
echo "Activity logging end-to-end verified."
