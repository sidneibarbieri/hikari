#!/usr/bin/env bash
# Clears the competition schedule from an installation and removes duplicate
# configuration keys, leaving the platform ready to receive a new execution.
#
# Preserves accounts, teams, challenges, solves and research data. To also
# drop participant data, use the CTFd reset page at /admin/reset.
#
# Duplicate keys matter because CTFd reads a single row per key: when the
# config table holds two rows named "end", the value in effect depends on row
# order, so the schedule can silently disagree with what the operator set.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"
COMPOSE_FILE=${COMPOSE_FILE:-"$LOCAL_DIR/docker-compose.yml"}

CTF_NAME=${CTF_NAME:-Hikari}

hikari_compose -f "$COMPOSE_FILE" exec -T ctfd env \
  CTF_NAME="$CTF_NAME" \
  python - <<'PY'
import os
import sys

from CTFd import create_app
from CTFd.models import Configs, db

SCHEDULE_KEYS = ("start", "end", "paused", "hikari_competition_key")

app = create_app()
with app.app_context():
    # One row per key. Keep the lowest id and drop the rest, so the value in
    # effect stops depending on row order.
    removed = 0
    seen = {}
    for row in Configs.query.order_by(Configs.id.asc()).all():
        if row.key in seen:
            db.session.delete(row)
            removed += 1
        else:
            seen[row.key] = row

    for key in SCHEDULE_KEYS:
        row = seen.get(key)
        if row is not None:
            row.value = ""

    ctf_name = seen.get("ctf_name")
    if ctf_name is not None:
        ctf_name.value = os.environ["CTF_NAME"]

    db.session.commit()
    sys.stdout.write(f"duplicate config rows removed: {removed}\n")
    sys.stdout.write("competition schedule cleared\n")
PY

hikari_mariadb -N -B -e \
  "UPDATE hikari_competition_runs
      SET status = 'cancelled'
    WHERE status IN ('scheduled', 'running', 'paused');
   SELECT CONCAT('executions cancelled: ', ROW_COUNT());" 2>/dev/null

echo "Installation ready for a new execution at /admin/hikari/competitions"
