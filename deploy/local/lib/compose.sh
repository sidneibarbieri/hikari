#!/usr/bin/env bash
# Resolves the Docker Compose command across Docker Desktop and legacy hosts.

set -euo pipefail

hikari_compose() {
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi

  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi

  echo "Docker Compose is required. Install the Docker Compose plugin or docker-compose." >&2
  return 127
}

# The database credentials differ between a development stack and an installed
# one. Reading them from the environment lets every verification script run
# against production, which is exactly when an operator needs to check it.
HIKARI_DB_USER=${HIKARI_DB_USER:-ctfd}
HIKARI_DB_PASSWORD=${HIKARI_DB_PASSWORD:-ctfd}
HIKARI_DB_ROOT_PASSWORD=${HIKARI_DB_ROOT_PASSWORD:-$HIKARI_DB_PASSWORD}
HIKARI_DB_NAME=${HIKARI_DB_NAME:-ctfd}

hikari_mariadb() {
  hikari_compose exec -T db mariadb \
    -u"$HIKARI_DB_USER" -p"$HIKARI_DB_PASSWORD" "$HIKARI_DB_NAME" "$@"
}

hikari_mariadb_root() {
  hikari_compose exec -T db mariadb -uroot -p"$HIKARI_DB_ROOT_PASSWORD" "$@"
}

hikari_mariadb_dump() {
  hikari_compose exec -T db mariadb-dump \
    -u"$HIKARI_DB_USER" -p"$HIKARI_DB_PASSWORD" --single-transaction "$HIKARI_DB_NAME"
}
