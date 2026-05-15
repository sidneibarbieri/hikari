#!/usr/bin/env bash
# Creates or updates the local automation admin without touching competition data.

set -euo pipefail

ADMIN_NAME=${ADMIN_NAME:-admin}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari_comp@2026}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
COMPOSE_FILE=${COMPOSE_FILE:-"$LOCAL_DIR/docker-compose.yml"}

docker-compose -f "$COMPOSE_FILE" exec -T ctfd env \
  ADMIN_NAME="$ADMIN_NAME" \
  ADMIN_EMAIL="$ADMIN_EMAIL" \
  ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  python - <<'PY'
import os
import sys

from CTFd import create_app
from CTFd.models import Users, db


admin_name = os.environ["ADMIN_NAME"]
admin_email = os.environ["ADMIN_EMAIL"]
admin_password = os.environ["ADMIN_PASSWORD"]

app = create_app()
with app.app_context():
    user = Users.query.filter_by(email=admin_email).first()
    if user is None:
        user = Users(
            name=admin_name,
            email=admin_email,
            password=admin_password,
            type="admin",
            verified=True,
            hidden=True,
        )
        db.session.add(user)
        action = "created"
    else:
        user.name = admin_name
        user.password = admin_password
        user.type = "admin"
        user.verified = True
        user.hidden = True
        action = "updated"
    db.session.commit()
    sys.stdout.write(f"automation admin {action}: {admin_email}\n")
PY
