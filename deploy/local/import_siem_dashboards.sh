#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
COMPOSE_FILE=${COMPOSE_FILE:-"$SCRIPT_DIR/docker-compose.yml"}
DASHBOARD_FILE=${DASHBOARD_FILE:-"$SCRIPT_DIR/kibana/hikari-siem.ndjson"}
DATA_VIEW_ID=${DATA_VIEW_ID:-competition1}
SIEM_DASHBOARD_ID=${SIEM_DASHBOARD_ID:-hikari-siem}

compose() {
  docker-compose -f "$COMPOSE_FILE" "$@"
}

kibana() {
  compose exec -T kibana curl -sS "$@"
}

wait_for_kibana() {
  for _ in {1..60}; do
    status=$(kibana "http://localhost:5601/hikari/kibana/api/status" \
      | jq -r '.status.overall.level // empty')
    if [[ "$status" == "available" ]]; then
      return 0
    fi
    sleep 2
  done
  echo "FAIL: Kibana did not become available"
  exit 1
}

import_saved_objects() {
  local tmp_path="/tmp/hikari-siem.ndjson"
  compose exec -T kibana sh -c "cat > '$tmp_path'" < "$DASHBOARD_FILE"
  response=$(kibana \
    -X POST "http://localhost:5601/hikari/kibana/api/saved_objects/_import?overwrite=true" \
    -H "kbn-xsrf: true" \
    --form "file=@$tmp_path")
  compose exec -T kibana rm -f "$tmp_path"
  success=$(echo "$response" | jq -r '.success')
  [[ "$success" == "true" ]] \
    || { echo "FAIL: saved object import returned $response"; exit 1; }
  echo "$response" | jq -r '"saved objects imported: \(.successCount)"'
}

delete_legacy_metric_objects() {
  local ids=(
    low-events-metric
    medium-events-metric
    high-events-metric
    critical-events-metric
  )
  local object_id
  for object_id in "${ids[@]}"; do
    kibana \
      -X DELETE "http://localhost:5601/hikari/kibana/api/saved_objects/visualization/$object_id?force=true" \
      -H "kbn-xsrf: true" >/dev/null || true
  done
}

set_default_data_view() {
  response=$(kibana \
    -X POST "http://localhost:5601/hikari/kibana/api/data_views/default" \
    -H "kbn-xsrf: true" \
    -H "Content-Type: application/json" \
    -d "$(jq -cn --arg id "$DATA_VIEW_ID" '{data_view_id:$id,force:true}')")
  acknowledged=$(echo "$response" | jq -r '.acknowledged')
  [[ "$acknowledged" == "true" ]] \
    || { echo "FAIL: default data view update returned $response"; exit 1; }
}

set_default_dashboard_route() {
  response=$(kibana \
    -X POST "http://localhost:5601/hikari/kibana/api/kibana/settings" \
    -H "kbn-xsrf: true" \
    -H "Content-Type: application/json" \
    -d "$(jq -cn --arg route "/app/dashboards#/view/$SIEM_DASHBOARD_ID" \
      '{changes:{"defaultRoute":$route}}')")
  value=$(echo "$response" | jq -r '.settings.defaultRoute.userValue // empty')
  [[ "$value" == "/app/dashboards#/view/$SIEM_DASHBOARD_ID" ]] \
    || { echo "FAIL: default route update returned $response"; exit 1; }
}

apply_siem_settings() {
  response=$(kibana \
    -X POST "http://localhost:5601/hikari/kibana/api/kibana/settings" \
    -H "kbn-xsrf: true" \
    -H "Content-Type: application/json" \
    -d '{"changes":{"theme:darkMode":true,"security.showInsecureClusterWarning":false}}')
  dark_mode=$(echo "$response" | jq -r '.settings["theme:darkMode"].userValue')
  [[ "$dark_mode" == "true" ]] \
    || { echo "FAIL: SIEM settings update returned $response"; exit 1; }
}

verify_dashboard() {
  dashboard=$(kibana \
    "http://localhost:5601/hikari/kibana/api/saved_objects/dashboard/$SIEM_DASHBOARD_ID")
  title=$(echo "$dashboard" | jq -r '.attributes.title // empty')
  [[ "$title" == "HIKARI SIEM" ]] \
    || { echo "FAIL: HIKARI SIEM dashboard missing"; exit 1; }
  panels=$(echo "$dashboard" | jq -r '.attributes.panelsJSON | fromjson | length')
  [[ "$panels" -ge 16 ]] \
    || { echo "FAIL: dashboard has too few panels ($panels)"; exit 1; }
  echo "PASS: HIKARI SIEM dashboard available with $panels panels"
}

[[ -f "$DASHBOARD_FILE" ]] \
  || { echo "FAIL: dashboard file missing: $DASHBOARD_FILE"; exit 1; }

wait_for_kibana
import_saved_objects
delete_legacy_metric_objects
set_default_data_view
set_default_dashboard_route
apply_siem_settings
verify_dashboard
