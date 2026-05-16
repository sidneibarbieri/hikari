#!/usr/bin/env bash
# Configure Elasticsearch Index Lifecycle Management for production ingest.
#
# Why this script exists
# ----------------------
# The local competition flow imports a bounded dataset once and reads it
# read-only during the event — no ILM needed. Production with continuous
# Logstash → Elasticsearch ingest grows the active index forever; without
# a rollover policy you eventually hit shard size limits, slow queries
# and disk pressure.
#
# What this script does
# ---------------------
# 1. Creates an ILM policy "hikari-events" with three phases:
#      - hot:    write phase, rollover at 30GB OR 30 days, whichever first
#      - warm:   shrink to 1 shard + force-merge, after 30 days in hot
#      - delete: drop the index after 90 days total
# 2. Creates an index template "hikari-events" that applies the policy to
#    any index matching "hikari-events-*" (Logstash should write to the
#    write-alias hikari-events).
# 3. Bootstraps the first hot index hikari-events-000001 and the alias.
#
# Idempotent: re-running is safe — existing policy/template/index are
# detected and left alone.

set -euo pipefail

ES_URL=${ES_URL:-http://localhost:9200}
POLICY_NAME=${POLICY_NAME:-hikari-events}
TEMPLATE_NAME=${TEMPLATE_NAME:-hikari-events}
INDEX_PATTERN="${POLICY_NAME}-*"
WRITE_ALIAS="${POLICY_NAME}"
BOOTSTRAP_INDEX="${POLICY_NAME}-000001"

echo "Configuring ILM at $ES_URL ..."

# Phase 1: policy
curl -sS -X PUT "$ES_URL/_ilm/policy/$POLICY_NAME" \
  -H "Content-Type: application/json" \
  -d '{
    "policy": {
      "phases": {
        "hot": {
          "actions": {
            "rollover": {
              "max_primary_shard_size": "30gb",
              "max_age": "30d"
            }
          }
        },
        "warm": {
          "min_age": "30d",
          "actions": {
            "shrink": { "number_of_shards": 1 },
            "forcemerge": { "max_num_segments": 1 }
          }
        },
        "delete": {
          "min_age": "90d",
          "actions": { "delete": {} }
        }
      }
    }
  }' | tee /tmp/ilm_policy_response.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
if data.get('acknowledged'):
    print('  policy: OK')
else:
    print('  policy:', data)" || { echo "  policy: FAILED"; exit 1; }

# Phase 2: index template wires the policy to new indices + sets the alias.
curl -sS -X PUT "$ES_URL/_index_template/$TEMPLATE_NAME" \
  -H "Content-Type: application/json" \
  -d '{
    "index_patterns": ["'"$INDEX_PATTERN"'"],
    "template": {
      "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 1,
        "index.lifecycle.name": "'"$POLICY_NAME"'",
        "index.lifecycle.rollover_alias": "'"$WRITE_ALIAS"'"
      }
    },
    "priority": 100
  }' | python3 -c "
import json, sys
data = json.load(sys.stdin)
if data.get('acknowledged'):
    print('  template: OK')
else:
    print('  template:', data)" || { echo "  template: FAILED"; exit 1; }

# Phase 3: bootstrap. Skip if the index already exists (idempotent).
exists=$(curl -sS -o /dev/null -w '%{http_code}' "$ES_URL/$BOOTSTRAP_INDEX")
if [[ "$exists" == "200" ]]; then
  echo "  bootstrap: skipped (index $BOOTSTRAP_INDEX exists)"
else
  curl -sS -X PUT "$ES_URL/$BOOTSTRAP_INDEX" \
    -H "Content-Type: application/json" \
    -d '{
      "aliases": {
        "'"$WRITE_ALIAS"'": { "is_write_index": true }
      }
    }' | python3 -c "
import json, sys
data = json.load(sys.stdin)
if data.get('acknowledged'):
    print('  bootstrap: OK')
else:
    print('  bootstrap:', data)" || { echo "  bootstrap: FAILED"; exit 1; }
fi

echo
echo "ILM configured. Point Logstash output at the alias '$WRITE_ALIAS':"
echo "  output { elasticsearch { hosts => [\"$ES_URL\"] index => \"$WRITE_ALIAS\" } }"
echo
echo "Inspect the rotation state any time with:"
echo "  curl -s $ES_URL/$WRITE_ALIAS/_ilm/explain | jq ."
