#!/usr/bin/env bash
# Smoke test of the data plane: produce one JSON record into the Kafka
# 'competition1' topic and assert that Elasticsearch indexes it through the
# Logstash pipeline. This isolates the data plane from the CTFd plugin's
# competition lifecycle (which currently requires zerotier setup).

set -euo pipefail

TOPIC=${TOPIC:-competition1}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"
COMPOSE_FILE=${COMPOSE_FILE:-"$LOCAL_DIR/docker-compose.yml"}

probe_id="hikari-smoke-$(date +%s)"
payload=$(jq -cn \
  --arg probe_id "$probe_id" \
  --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{
    event: "smoke",
    probe_id: $probe_id,
    "@timestamp": $timestamp,
    "Source IP": "198.51.100.42",
    "Destination IP": "203.0.113.12",
    "Destination Port": "443",
    "Threat Severity (custom)": "high",
    "Fortinet Message (custom)": "Synthetic dashboard validation event",
    "Event Name": "network_connection",
    "URL (custom)": "https://validation.hikari.local/indicator",
    "Command Line (custom)": "curl https://validation.hikari.local/indicator"
    ,"udm.principal.location": "headquarters"
    ,"udm.principal.location.country": "BR"
  }')

elasticsearch_search() {
  local path=$1 query_body=$2
  hikari_compose -f "$COMPOSE_FILE" exec -T elasticsearch \
    curl -sS -H 'Content-Type: application/json' \
    -X POST "http://localhost:9200/$path" -d "$query_body"
}

echo "producing one record to topic '$TOPIC' with probe_id=$probe_id ..."
echo "$payload" | hikari_compose -f "$COMPOSE_FILE" exec -T kafka \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 --topic "$TOPIC" >/dev/null
echo "produced."

echo "polling Elasticsearch for the document ..."
deadline=$((SECONDS + 30))
query=$(jq -cn --arg probe "$probe_id" \
  '{query: {match_phrase: {probe_id: $probe}}}')
hits=0
while (( SECONDS < deadline )); do
  hits=$(elasticsearch_search "$TOPIC/_search" "$query" \
    | jq -r '.hits.total.value // 0')
  if [[ "$hits" -ge 1 ]]; then
    break
  fi
  sleep 2
done

if [[ "$hits" -lt 1 ]]; then
  echo "FAIL: probe_id=$probe_id not found in Elasticsearch after 30s"
  elasticsearch_search "$TOPIC/_search" "$query" | jq .
  exit 1
fi

indexed_country=$(elasticsearch_search "$TOPIC/_search" "$query" \
  | jq -r '.hits.hits[0]._source["udm.principal.location.country"] // empty')
if [[ "$indexed_country" != "BR" ]]; then
  echo "FAIL: competition index did not preserve dotted source fields"
  exit 1
fi

echo "PASS: produced record reached Elasticsearch (index=$TOPIC, probe_id=$probe_id, hits=$hits)"
