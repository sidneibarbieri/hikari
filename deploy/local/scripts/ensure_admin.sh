#!/usr/bin/env bash
# Creates or updates the administrator accounts without touching competition data.
#
# The technical administrator is an idempotent upsert. An optional second
# administrator is created only when the operator provides all its fields.

set -euo pipefail

ADMIN_NAME=${ADMIN_NAME:-admin}
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@hikari.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-hikari_comp@2026}

OWNER_NAME=${OWNER_NAME:-}
OWNER_EMAIL=${OWNER_EMAIL:-}
OWNER_PASSWORD=${OWNER_PASSWORD:-}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOCAL_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
source "$LOCAL_DIR/lib/compose.sh"
COMPOSE_FILE=${COMPOSE_FILE:-"$LOCAL_DIR/docker-compose.yml"}

upsert_admin() {
  local account_name=$1
  local account_email=$2
  local account_password=$3

  hikari_compose -f "$COMPOSE_FILE" exec -T ctfd env \
    ACCOUNT_NAME="$account_name" \
    ACCOUNT_EMAIL="$account_email" \
    ACCOUNT_PASSWORD="$account_password" \
    python - <<'PY'
import os
import sys

from CTFd import create_app
from CTFd.models import Users, db


account_name = os.environ["ACCOUNT_NAME"]
account_email = os.environ["ACCOUNT_EMAIL"]
account_password = os.environ["ACCOUNT_PASSWORD"]

app = create_app()
with app.app_context():
    # Username login resolves filter_by(name=...).first(), which returns the
    # lowest id. Claim that row so the credential always reaches this account.
    canonical = (
        Users.query
        .filter_by(name=account_name)
        .order_by(Users.id.asc())
        .first()
    )
    if canonical is None:
        canonical = Users.query.filter(Users.email.ilike(account_email)).first()
    if canonical is None:
        canonical = Users(name=account_name, email=account_email, type="admin")
        db.session.add(canonical)
        db.session.flush()
        action = "created"
    else:
        action = "updated"

    # Drop same-name duplicates before writing the email, so the unique
    # constraint on email cannot fail during flush.
    duplicates = (
        Users.query
        .filter(Users.name == account_name, Users.id != canonical.id)
        .all()
    )
    for duplicate in duplicates:
        db.session.delete(duplicate)
    db.session.flush()

    canonical.name = account_name
    canonical.email = account_email
    canonical.password = account_password
    canonical.type = "admin"
    canonical.verified = True
    canonical.hidden = True
    db.session.commit()
    sys.stdout.write(f"admin {action}: {account_name} <{account_email}> (id={canonical.id})\n")
PY
}

upsert_admin "$ADMIN_NAME" "$ADMIN_EMAIL" "$ADMIN_PASSWORD"

if [[ -n "$OWNER_NAME$OWNER_EMAIL$OWNER_PASSWORD" ]]; then
  [[ -n "$OWNER_NAME" && -n "$OWNER_EMAIL" && -n "$OWNER_PASSWORD" ]] || {
    echo "OWNER_NAME, OWNER_EMAIL e OWNER_PASSWORD devem ser informados juntos." >&2
    exit 1
  }
  upsert_admin "$OWNER_NAME" "$OWNER_EMAIL" "$OWNER_PASSWORD"
fi
