#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE=${COMPOSE_FILE:-"$LOCAL_DIR/docker-compose.yml"}
DATA_VIEW_TITLE=${DATA_VIEW_TITLE:-competition1}
TIME_FIELD=${TIME_FIELD:-@timestamp}

compose() {
  docker-compose -f "$COMPOSE_FILE" "$@"
}

kibana() {
  compose exec -T kibana curl -sS "$@"
}

elasticsearch() {
  compose exec -T elasticsearch curl -sS "$@"
}

wait_for_index() {
  for _ in {1..30}; do
    if elasticsearch "http://localhost:9200/$DATA_VIEW_TITLE" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "FAIL: Elasticsearch index $DATA_VIEW_TITLE was not found"
  exit 1
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

find_data_view_id() {
  kibana "http://localhost:5601/hikari/kibana/api/data_views" \
    | jq -r --arg title "$DATA_VIEW_TITLE" \
      '.data_view[]? | select(.title == $title) | .id' \
    | head -1
}

create_data_view() {
  response=$(kibana \
    -X POST "http://localhost:5601/hikari/kibana/api/data_views/data_view" \
    -H "kbn-xsrf: true" \
    -H "Content-Type: application/json" \
    -d "$(jq -cn \
      --arg title "$DATA_VIEW_TITLE" \
      --arg time_field "$TIME_FIELD" \
      '{data_view:{title:$title,name:$title,timeFieldName:$time_field}}')")
  echo "$response" | jq -r '.data_view.id'
}

set_default_data_view() {
  local data_view_id=$1
  response=$(kibana \
    -X POST "http://localhost:5601/hikari/kibana/api/data_views/default" \
    -H "kbn-xsrf: true" \
    -H "Content-Type: application/json" \
    -d "$(jq -cn --arg id "$data_view_id" \
      '{data_view_id:$id,force:true}')")
  acknowledged=$(echo "$response" | jq -r '.acknowledged')
  [[ "$acknowledged" == "true" ]] \
    || { echo "FAIL: default data view update returned $response"; exit 1; }
}

set_time_range_defaults() {
  response=$(kibana \
    -X POST "http://localhost:5601/hikari/kibana/api/kibana/settings" \
    -H "kbn-xsrf: true" \
    -H "Content-Type: application/json" \
    -d '{"changes":{"timepicker:timeDefaults":"{\"from\":\"now-10y\",\"to\":\"now\"}"}}')
  value=$(echo "$response" \
    | jq -r '.settings["timepicker:timeDefaults"].userValue // empty')
  [[ "$value" == '{"from":"now-10y","to":"now"}' ]] \
    || { echo "FAIL: time range defaults update returned $response"; exit 1; }
}

wait_for_index
wait_for_kibana

data_view_id=$(find_data_view_id)
if [[ -z "$data_view_id" ]]; then
  data_view_id=$(create_data_view)
  echo "data view created: $DATA_VIEW_TITLE"
else
  echo "data view already exists: $DATA_VIEW_TITLE"
fi

set_default_data_view "$data_view_id"
echo "default data view set: $DATA_VIEW_TITLE"
set_time_range_defaults
echo "default time range set"
