#!/usr/bin/env bash
# =============================================================================
# import_siem_dashboards.sh — Build the Hikari SIEM dashboard in Kibana 8.19
#
# Instead of importing an NDJSON bundle (which breaks panelRefName references
# due to Kibana's import-time normalisation), this script runs the Python
# rebuild script directly inside the CTFd container, where it reaches Kibana
# by service name (http://kibana:5601/…) and creates every saved object via
# the REST POST API with exact reference names.
#
# Usage:
#   bash deploy/local/import_siem_dashboards.sh
#   COMPOSE_FILE=/path/to/docker-compose.yml bash import_siem_dashboards.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE=${COMPOSE_FILE:-"$LOCAL_DIR/docker-compose.yml"}
REBUILD_SCRIPT="$LOCAL_DIR/kibana/rebuild_siem_dashboard.py"
DATA_VIEW_ID=${DATA_VIEW_ID:-competition1}
SIEM_DASHBOARD_ID=${SIEM_DASHBOARD_ID:-hikari-siem}

# Internal service name — Kibana is only reachable by this hostname from
# other containers on the same Docker Compose network.
KIBANA_INTERNAL_URL="http://kibana:5601/hikari/kibana"

compose() {
  docker-compose -f "$COMPOSE_FILE" "$@"
}

kibana() {
  compose exec -T kibana curl -sS "$@"
}

# ---- 1. Sanity checks -------------------------------------------------------

[[ -f "$REBUILD_SCRIPT" ]] \
  || { echo "FAIL: rebuild script missing: $REBUILD_SCRIPT"; exit 1; }

# ---- 2. Wait for Kibana -----------------------------------------------------

wait_for_kibana() {
  echo "Waiting for Kibana to become available..."
  for _ in {1..60}; do
    status=$(kibana "http://localhost:5601/hikari/kibana/api/status" \
      | jq -r '.status.overall.level // empty' 2>/dev/null || true)
    if [[ "$status" == "available" ]]; then
      echo "Kibana is ready."
      return 0
    fi
    sleep 2
  done
  echo "FAIL: Kibana did not become available within 120 s"
  exit 1
}

# ---- 3. Remove legacy orphan dashboards -------------------------------------

delete_legacy_dashboards() {
  # The original Hikari dashboard.zip (Aug 2025) included a single-panel
  # "SOC Dashboard - competition1" search saved-object. Delete it idempotently
  # so reviewers end up with exactly one curated dashboard.
  local ids=(
    soc-dashboard-competition1
    lista-de-conexoes-recentes
  )
  local object_id
  for object_id in "${ids[@]}"; do
    kibana \
      -X DELETE "http://localhost:5601/hikari/kibana/api/saved_objects/dashboard/$object_id?force=true" \
      -H "kbn-xsrf: true" >/dev/null 2>&1 || true
    kibana \
      -X DELETE "http://localhost:5601/hikari/kibana/api/saved_objects/search/$object_id?force=true" \
      -H "kbn-xsrf: true" >/dev/null 2>&1 || true
  done
  echo "Legacy orphan dashboards cleaned up."
}

# ---- 4. Run the Python rebuild script inside CTFd ---------------------------
#
# The CTFd container has Python 3 + the same Docker Compose network, so it
# can reach Kibana by service hostname. We copy the script into /tmp to avoid
# any path-mapping issues and pass KIBANA_BASE via environment variable.

rebuild_dashboard() {
  local remote_script="/tmp/rebuild_siem_dashboard.py"

  echo "Copying rebuild script into CTFd container..."
  compose cp "$REBUILD_SCRIPT" ctfd:"$remote_script" 2>/dev/null \
    || docker cp "$REBUILD_SCRIPT" "$(compose ps -q ctfd)":/tmp/rebuild_siem_dashboard.py

  echo "Running rebuild script (KIBANA_BASE=$KIBANA_INTERNAL_URL)..."
  compose exec -T -e "KIBANA_BASE=$KIBANA_INTERNAL_URL" ctfd \
    python3 "$remote_script"

  echo "Cleaning up temporary script..."
  compose exec -T ctfd rm -f "$remote_script" || true
}

# ---- 5. Post-build settings -------------------------------------------------

set_default_data_view() {
  response=$(kibana \
    -X POST "http://localhost:5601/hikari/kibana/api/data_views/default" \
    -H "kbn-xsrf: true" \
    -H "Content-Type: application/json" \
    -d "$(jq -cn --arg id "$DATA_VIEW_ID" '{data_view_id:$id,force:true}')")
  acknowledged=$(echo "$response" | jq -r '.acknowledged')
  [[ "$acknowledged" == "true" ]] \
    || { echo "FAIL: default data view update returned $response"; exit 1; }
  echo "Default data view set to: $DATA_VIEW_ID"
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
  echo "Default Kibana route set to dashboard: $SIEM_DASHBOARD_ID"
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
  echo "Dark mode and security warning suppression applied."
}

# ---- 6. Verify --------------------------------------------------------------

verify_dashboard() {
  dashboard=$(kibana \
    "http://localhost:5601/hikari/kibana/api/saved_objects/dashboard/$SIEM_DASHBOARD_ID")
  title=$(echo "$dashboard" | jq -r '.attributes.title // empty')
  [[ "$title" == "HIKARI SIEM" ]] \
    || { echo "FAIL: HIKARI SIEM dashboard missing after rebuild"; exit 1; }
  panels=$(echo "$dashboard" | jq -r '.attributes.panelsJSON | fromjson | length')
  # The rebuild script creates 13 panels (12 visualizations + 1 search).
  [[ "$panels" -ge 13 ]] \
    || { echo "FAIL: dashboard has too few panels ($panels, expected ≥13)"; exit 1; }
  echo "PASS: HIKARI SIEM dashboard available with $panels panels"
}

# ---- Main -------------------------------------------------------------------

wait_for_kibana
delete_legacy_dashboards
rebuild_dashboard
set_default_data_view
set_default_dashboard_route
apply_siem_settings
verify_dashboard

echo ""
echo "SIEM dashboard import complete."
