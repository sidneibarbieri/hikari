#!/usr/bin/env bash
# Sends a Kibana search request through the authenticated proxy and verifies
# the activity record carries structured forensic facts.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari_comp@2026}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE=${COMPOSE_FILE:-"$LOCAL_DIR/docker-compose.yml"}

jar=$(mktemp)
trap 'rm -f "$jar" /tmp/hikari-classifier-*.html' EXIT

login_page=/tmp/hikari-classifier-login.html
curl -sS -c "$jar" -b "$jar" -o "$login_page" "$CTFD_URL/login"
nonce=$(grep -oE 'name="nonce"[^>]*value="[^"]+"' "$login_page" \
  | head -1 | sed -E 's/.*value="([^"]+)".*/\1/')

code=$(curl -sS -c "$jar" -b "$jar" -o /dev/null -w '%{http_code}' \
  -X POST "$CTFD_URL/login" \
  --data-urlencode "name=$ADMIN_EMAIL" \
  --data-urlencode "password=$ADMIN_PASSWORD" \
  --data-urlencode "nonce=$nonce")
[[ "$code" == "302" ]] || { echo "admin login returned $code"; exit 1; }
echo "PASS: admin authenticated"

probe_id="classifier-probe-$(date +%s)"
gte="2026-05-01T00:00:00Z"
lte="2026-05-12T23:59:59Z"
body=$(jq -cn --arg probe "$probe_id" --arg gte "$gte" --arg lte "$lte" '{
  index: "competition1",
  size: 10,
  query: {
    bool: {
      must: [
        { match: { event: "alert" } }
      ],
      filter: [
        { range: { "@timestamp": { gte: $gte, lte: $lte } } },
        { term: { probe_marker: $probe } }
      ],
      should: [
        { match: { severity: "high" } }
      ]
    }
  },
  aggs: {
    by_event: { terms: { field: "event.keyword" } }
  },
  sort: [{ "@timestamp": "desc" }]
}')

code=$(curl -sS -c "$jar" -b "$jar" \
  -o /tmp/hikari-classifier-resp.json \
  -w '%{http_code}' \
  -H "Content-Type: application/json" \
  -H "kbn-xsrf: true" \
  -X POST "$CTFD_URL/hikari/kibana/internal/search/es" \
  -d "$body")
echo "kibana proxy returned HTTP $code"

sleep 2

payload=$(docker-compose -f "$COMPOSE_FILE" exec -T db \
  mariadb -uctfd -pctfd ctfd -N -B --raw -e \
  "SELECT payload FROM hikari_activity WHERE event_type='kibana.query' ORDER BY id DESC LIMIT 1;")

[[ -n "$payload" ]] || { echo "FAIL: no kibana.query activity row was written"; exit 1; }
echo "PASS: kibana.query activity row exists"

assert_jq() {
  local jq_expr=$1 label=$2 expected=$3 actual
  actual=$(printf '%s' "$payload" | jq -r "$jq_expr")
  if [[ "$actual" != "$expected" ]]; then
    echo "FAIL: $label expected '$expected' got '$actual'"
    echo "payload: $payload"
    exit 1
  fi
  echo "PASS: $label = $actual"
}

assert_jq '.kibana.query_kind' "kibana.query_kind" "search"
assert_jq '.kibana.indices[0]' "kibana.indices[0]" "competition1"
assert_jq '.kibana.has_query' "kibana.has_query" "true"
assert_jq '.kibana.has_filters' "kibana.has_filters" "true"
assert_jq '.kibana.has_aggs' "kibana.has_aggs" "true"
assert_jq '.kibana.has_sort' "kibana.has_sort" "true"
assert_jq '.kibana.must_count' "kibana.must_count" "1"
assert_jq '.kibana.should_count' "kibana.should_count" "1"
assert_jq '.kibana.filter_count' "kibana.filter_count" "2"
assert_jq '.kibana.size' "kibana.size" "10"
assert_jq '.kibana.time_range_field' "kibana.time_range_field" "@timestamp"
assert_jq '.kibana.time_range_gte' "kibana.time_range_gte" "$gte"
assert_jq '.kibana.time_range_lte' "kibana.time_range_lte" "$lte"

echo
echo "Kibana forensic classifier verified."
