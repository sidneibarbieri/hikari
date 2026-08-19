#!/usr/bin/env bash
# Proves a scheduled execution starts by itself when its hour arrives.
#
# The rehearsal and the event itself are scheduled, not started by hand. If the
# promotion from scheduled to running never fires, nobody plays and the reason
# is invisible: the execution sits there looking correct.

set -euo pipefail

CTFD_URL=${CTFD_URL:-http://localhost:8000}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"

stamp=$(date +%s)
chave="partida-$stamp"
trap 'hikari_mariadb -e "DELETE FROM hikari_competition_runs WHERE \`key\` = '"'"'$chave'"'"';" >/dev/null 2>&1 || true' EXIT

estado() {
  hikari_mariadb -N -B -e \
    "SELECT status FROM hikari_competition_runs WHERE \`key\` = '$chave';" | tr -d '[:space:]'
}

echo "== 1. uma execução agendada para daqui a instantes =="
# Encerra o que estiver ativo, porque a instalação controla uma execução por vez.
hikari_mariadb -e \
  "UPDATE hikari_competition_runs SET status = 'finished'
    WHERE status IN ('scheduled','running','paused');" > /dev/null

hikari_compose exec -T ctfd python - <<PY > /dev/null
from datetime import datetime, timedelta
from CTFd import create_app
from CTFd.models import db

app = create_app()
with app.app_context():
    from CTFd.plugins.hikari_plugin.hikari_competitions import service
    from CTFd.plugins.hikari_plugin.hikari_competitions.models import CompetitionRun

    agora = datetime.utcnow()
    corrida = CompetitionRun(
        key="$chave", name="Partida automática", scoring_mode="teams", duration_minutes=60
    )
    db.session.add(corrida)
    db.session.commit()
    service.schedule_run(corrida, agora + timedelta(seconds=5), agora)
PY

[[ "$(estado)" == "scheduled" ]] || { echo "FAIL: a execução não ficou agendada"; exit 1; }
echo "PASS: agendada para daqui a cinco segundos"

echo
echo "== 2. o horário chega e alguém abre uma página =="
until [[ "$(estado)" == "running" ]]; do
  curl -sS -o /dev/null "$CTFD_URL/" || true
  sleep 2
done
echo "PASS: a execução passou sozinha para em andamento"

echo
echo "== 3. o prazo do CTFd acompanha a execução =="
inicio=$(hikari_mariadb -N -B -e "SELECT value FROM config WHERE \`key\` = 'start';" | tr -d '[:space:]')
fim=$(hikari_mariadb -N -B -e "SELECT value FROM config WHERE \`key\` = 'end';" | tr -d '[:space:]')
agora=$(date +%s)
[[ "$inicio" -le "$agora" ]] || { echo "FAIL: o CTFd ainda considera a competição futura"; exit 1; }
[[ "$fim" -gt "$agora" ]] || { echo "FAIL: o CTFd considera a competição encerrada"; exit 1; }
echo "PASS: janela aberta no CTFd, terminando em $(( (fim - agora) / 60 )) minutos"

hikari_mariadb -e \
  "UPDATE hikari_competition_runs SET status = 'finished' WHERE \`key\` = '$chave';" > /dev/null

echo
echo "Partida automática verificada."
