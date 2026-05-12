#!/usr/bin/env bash
# Local stack smoke test. Runs from deploy/local. Each check exits non-zero on
# failure with a one-line reason on stderr. Run with `bash smoke.sh` or
# `bash smoke.sh --wait` to poll services until they are ready.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

WAIT=${1:-}
CTFD_URL=${CTFD_URL:-http://localhost:8000}
COMPOSE_FILE=${COMPOSE_FILE:-$SCRIPT_DIR/docker-compose.yml}

fail() { echo "FAIL: $*" >&2; exit 1; }
ok()   { echo "PASS: $*"; }

wait_http() {
  local url=$1 label=$2 timeout=${3:-240}
  local deadline=$((SECONDS + timeout))
  while (( SECONDS < deadline )); do
    if curl -fsS -o /dev/null --max-time 3 "$url"; then
      ok "$label reachable at $url"; return 0
    fi
    sleep 3
  done
  fail "$label did not become reachable at $url within ${timeout} seconds"
}

wait_kibana_status() {
  local timeout=${1:-360} body
  local deadline=$((SECONDS + timeout))
  while (( SECONDS < deadline )); do
    body=$(internal_kibana_status || true)
    if echo "$body" | jq -e '.status.overall.level == "available"' >/dev/null 2>&1; then
      ok "Kibana reports overall status available"
      return 0
    fi
    sleep 5
  done
  fail "Kibana did not report available within ${timeout} seconds"
}

check_compose_state() {
  local unhealthy
  unhealthy=$(docker-compose -f "$COMPOSE_FILE" ps --format json 2>/dev/null | \
    jq -r 'select(.State!="running" and .State!="exited") | .Name' 2>/dev/null || true)
  [[ -z "$unhealthy" ]] || fail "containers not running: $unhealthy"
  ok "all compose services are running"
}

check_ctfd_http() {
  local code
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "$CTFD_URL/")
  case "$code" in
    200|301|302) ok "CTFd responded with $code at $CTFD_URL/" ;;
    *) fail "CTFd returned unexpected status $code" ;;
  esac
}

check_kibana_status() {
  local body
  body=$(internal_kibana_status)
  echo "$body" | jq -e '.status.overall.level == "available"' >/dev/null \
    || fail "Kibana status not available: $(echo "$body" | jq -c '.status.overall // .')"
  ok "Kibana reports overall status available"
}

check_elasticsearch() {
  local status
  status=$(internal_elasticsearch_health | jq -r '.status')
  [[ "$status" == "green" || "$status" == "yellow" ]] \
    || fail "Elasticsearch cluster status is $status"
  ok "Elasticsearch cluster is $status"
}

check_kafka_topics() {
  docker-compose -f "$COMPOSE_FILE" exec -T kafka /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server localhost:9092 --list >/dev/null \
    || fail "Kafka topic list command failed"
  ok "Kafka responded to topics listing"
}

internal_kibana_status() {
  docker-compose -f "$COMPOSE_FILE" exec -T ctfd python - <<'PY'
import requests
import sys

response = requests.get("http://kibana:5601/hikari/kibana/api/status", timeout=10)
sys.stdout.write(response.text)
PY
}

internal_elasticsearch_health() {
  docker-compose -f "$COMPOSE_FILE" exec -T elasticsearch \
    curl -fsS --max-time 5 http://localhost:9200/_cluster/health
}

main() {
  if [[ "$WAIT" == "--wait" ]]; then
    wait_http "$CTFD_URL/" "CTFd"
    wait_kibana_status
  fi
  check_compose_state
  check_ctfd_http
  check_elasticsearch
  if [[ "$WAIT" != "--wait" ]]; then
    check_kibana_status
  fi
  check_kafka_topics
  echo
  echo "All smoke checks passed."
}

main "$@"
