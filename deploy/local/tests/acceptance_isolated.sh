#!/usr/bin/env bash
# Runs acceptance checks in a disposable Compose project.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"

stamp=$(date +%s)
PROJECT=${HIKARI_ACCEPTANCE_PROJECT:-"hikariaccept${stamp}"}
LOCK_DIR="${TMPDIR:-/tmp}/hikari-acceptance.lock"

# A run killed by the operator, by the out-of-memory killer or by a reboot
# leaves the directory behind. Without this check the stale lock would block
# every future run with no way out but deleting it by hand.
claim_lock() {
  mkdir "$LOCK_DIR" 2>/dev/null && return 0

  local owner_pid
  owner_pid=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
  if [[ -n "$owner_pid" ]] && kill -0 "$owner_pid" 2>/dev/null; then
    return 1
  fi

  echo "Reclaiming a lock left by run ${owner_pid:-unknown}, which is no longer running." >&2
  rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR" 2>/dev/null
}

if ! claim_lock; then
  cat >&2 <<TXT
Another isolated acceptance run is already active (PID $(cat "$LOCK_DIR/pid" 2>/dev/null)).
Wait for it to finish before starting another disposable stack.
TXT
  exit 4
fi
printf '%s\n' "$$" > "$LOCK_DIR/pid"

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
  rm -rf "$LOCK_DIR"
}
trap cleanup EXIT

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for the acceptance suite." >&2
  exit 127
fi

# A disposable stack runs its own Elasticsearch beside the operating one. On a
# host that cannot feed both, the kernel reclaims memory from whichever it
# picks, and the loser is usually the stack holding real data. Say so before
# starting rather than leaving the operator to discover a dead index later.
REQUIRED_MEMORY_GIB=${HIKARI_ACCEPTANCE_MEMORY_GIB:-10}

# Both readings let a real failure surface. Silencing them would turn a broken
# Docker into "nothing is running, plenty of memory" and disable this guard at
# the exact moment it is needed.
operating_container_count() {
  hikari_compose -f "$COMPOSE_FILE" -p local ps -q --status running | wc -l | tr -d ' '
}

docker_memory_gib() {
  docker info --format '{{.MemTotal}}' | awk '{printf "%d", $1 / 1024 / 1024 / 1024}'
}

if [[ "$(operating_container_count)" != "0" ]]; then
  available_gib=$(docker_memory_gib)
  if [[ "$available_gib" -lt "$REQUIRED_MEMORY_GIB" ]]; then
    cat >&2 <<TXT
A stack de operação está no ar e o Docker tem ${available_gib} GiB, abaixo dos
${REQUIRED_MEMORY_GIB} GiB necessários para as duas ao mesmo tempo. Rodar assim
derruba o Elasticsearch de uma delas, normalmente a que guarda dados reais.

Pare a stack de operação, rode a suíte e suba de novo:

  docker-compose -p local stop
  bash tests/acceptance_isolated.sh
  docker-compose -p local start

Para ignorar esta checagem: HIKARI_ACCEPTANCE_MEMORY_GIB=0
TXT
    exit 3
  fi
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
