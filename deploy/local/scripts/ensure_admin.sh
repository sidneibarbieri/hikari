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
    # Resolve the canonical admin: prefer the lowest-id user with this name
    # (CTFd username login returns filter_by(name=...).first() which is
    # ordered by primary key, so the lowest id wins).
    canonical = (
        Users.query
        .filter_by(name=admin_name)
        .order_by(Users.id.asc())
        .first()
    )
    if canonical is None:
        canonical = Users.query.filter_by(email=admin_email).first()
    if canonical is None:
        canonical = Users(name=admin_name, email=admin_email, type="admin")
        db.session.add(canonical)
        db.session.flush()
        action = "created"
    else:
        action = "updated"

    # Remove duplicate admins with the same name before touching email to
    # avoid unique-constraint violations on flush.
    duplicates = (
        Users.query
        .filter(Users.name == admin_name, Users.id != canonical.id)
        .all()
    )
    for dup in duplicates:
        db.session.delete(dup)
    db.session.flush()  # delete duplicates first so email is now free

    canonical.name = admin_name
    canonical.email = admin_email
    canonical.password = admin_password
    canonical.type = "admin"
    canonical.verified = True
    canonical.hidden = True
    db.session.commit()
    sys.stdout.write(f"automation admin {action}: {admin_email} (id={canonical.id})\n")
PY
