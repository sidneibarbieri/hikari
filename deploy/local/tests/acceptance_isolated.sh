#!/usr/bin/env bash
# Runs acceptance checks in a disposable Compose project.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"

stamp=$(date +%s)
PROJECT=${HIKARI_ACCEPTANCE_PROJECT:-"hikariaccept${stamp}"}

available_port() {
  python3 - <<'PY'
import socket
import sys

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
    listener.bind(("127.0.0.1", 0))
    sys.stdout.write(str(listener.getsockname()[1]))
PY
}

CTFD_PORT=${HIKARI_ACCEPTANCE_PORT:-$(available_port)}
MAIL_UI_PORT=${HIKARI_ACCEPTANCE_MAIL_UI_PORT:-$(available_port)}
MAIL_SMTP_PORT=${HIKARI_ACCEPTANCE_MAIL_SMTP_PORT:-$(available_port)}
COMPOSE_FILE="$LOCAL_DIR/docker-compose.yml"
CTFD_URL="http://localhost:${CTFD_PORT}"

cleanup() {
  hikari_compose -f "$COMPOSE_FILE" -p "$PROJECT" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for the acceptance suite." >&2
  exit 127
fi

export COMPOSE_PROJECT_NAME="$PROJECT"
export CTFD_PORT MAIL_UI_PORT MAIL_SMTP_PORT CTFD_URL
export HIKARI_ACCEPTANCE_CONTEXT=1
# Keep the disposable verification stack below the capacity of a developer
# workstation that may already be running a local competition.
export ES_JAVA_OPTS=${HIKARI_ACCEPTANCE_ES_JAVA_OPTS:--Xms256m -Xmx512m}
export KIBANA_NODE_OPTIONS=${HIKARI_ACCEPTANCE_KIBANA_NODE_OPTIONS:---max-old-space-size=512}
export KAFKA_HEAP_OPTS=${HIKARI_ACCEPTANCE_KAFKA_HEAP_OPTS:--Xms192m -Xmx384m}
export LS_JAVA_OPTS=${HIKARI_ACCEPTANCE_LS_JAVA_OPTS:--Xms128m -Xmx256m}
# The reproducibility path must not depend on an operator's OAuth credentials.
export HIKARI_GOOGLE_CLIENT_ID=
export HIKARI_GOOGLE_CLIENT_SECRET=

echo "Starting isolated acceptance stack: $PROJECT"
hikari_compose -f "$COMPOSE_FILE" -p "$PROJECT" up -d --build

cd "$LOCAL_DIR"
bash run_acceptance.sh
