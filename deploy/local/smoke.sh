#!/usr/bin/env bash
# Local stack smoke test. Runs from deploy/local. Each check exits non-zero on
# failure with a one-line reason on stderr. Run with `bash smoke.sh` or
# `bash smoke.sh --wait` to poll services until they are ready.

set -euo pipefail

WAIT=${1:-}
CTFD_URL=${CTFD_URL:-http://localhost:8000}
KIBANA_URL=${KIBANA_URL:-http://localhost:5601}
ES_URL=${ES_URL:-http://localhost:9200}

fail() { echo "FAIL: $*" >&2; exit 1; }
ok()   { echo "PASS: $*"; }

wait_http() {
  local url=$1 label=$2 deadline=$((SECONDS + 240))
  while (( SECONDS < deadline )); do
    if curl -fsS -o /dev/null --max-time 3 "$url"; then
      ok "$label reachable at $url"; return 0
    fi
    sleep 3
  done
  fail "$label did not become reachable at $url within $((deadline)) seconds"
}

check_compose_state() {
  local unhealthy
  unhealthy=$(docker-compose ps --format json 2>/dev/null | \
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
  body=$(curl -sS --max-time 10 "$KIBANA_URL/api/status")
  echo "$body" | jq -e '.status.overall.level == "available"' >/dev/null \
    || fail "Kibana status not available: $(echo "$body" | jq -c '.status.overall // .')"
  ok "Kibana reports overall status available"
}

check_elasticsearch() {
  local status
  status=$(curl -sS --max-time 5 "$ES_URL/_cluster/health" | jq -r '.status')
  [[ "$status" == "green" || "$status" == "yellow" ]] \
    || fail "Elasticsearch cluster status is $status"
  ok "Elasticsearch cluster is $status"
}

check_kafka_topics() {
  docker-compose exec -T kafka /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server localhost:9092 --list >/dev/null \
    || fail "Kafka topic list command failed"
  ok "Kafka responded to topics listing"
}

main() {
  if [[ "$WAIT" == "--wait" ]]; then
    wait_http "$CTFD_URL/" "CTFd"
    wait_http "$KIBANA_URL/api/status" "Kibana"
    wait_http "$ES_URL/_cluster/health" "Elasticsearch"
  fi
  check_compose_state
  check_ctfd_http
  check_elasticsearch
  check_kibana_status
  check_kafka_topics
  echo
  echo "All smoke checks passed."
}

main "$@"
