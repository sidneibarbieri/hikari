#!/usr/bin/env bash
# Rebuilds the SIEM haystack from the log files of the currently active
# challenges.
#
# The index the competitors hunt through belongs to the challenge set, not to
# an edition. Whenever the active challenges change — a new library imported,
# a challenge hidden or removed — the index has to be rebuilt so people only
# ever see the telemetry of the challenges actually in play.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"

CONTAINER_SCRIPT=/tmp/rebuild_competition_data.py

running=$(hikari_mariadb -N -e \
  "SELECT COUNT(*) FROM hikari_competition_runs WHERE status IN ('scheduled','running','paused');" \
  | tr -d '[:space:]')
if [[ "$running" != "0" ]]; then
  echo "ERRO: há uma execução agendada, em andamento ou pausada. Rebuild do SIEM" >&2
  echo "      trocaria os dados sob os pés de quem está investigando." >&2
  exit 1
fi

echo "Reconstruindo o índice do SIEM a partir dos desafios ativos..."
hikari_compose cp "$SCRIPT_DIR/rebuild_competition_data.py" "ctfd:$CONTAINER_SCRIPT"
hikari_compose exec -T ctfd python "$CONTAINER_SCRIPT"

documents=$(hikari_compose exec -T elasticsearch curl -fsS \
  "http://localhost:9200/competition1/_count" \
  | jq '.count')
echo "Índice competition1 com $documents documento(s)."
