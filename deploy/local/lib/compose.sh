#!/usr/bin/env bash
# Resolves the Docker Compose command and points it at the stack that is
# actually running.

set -euo pipefail

HIKARI_LIB_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
HIKARI_LOCAL_DIR=$(cd "$HIKARI_LIB_DIR/.." && pwd)

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

hikari_container_env() {
  docker inspect "$1" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
    | sed -n "s/^$2=//p" | head -1
}

# A production install overlays a second compose file on the development one, so
# a helper that assumes a single file reports every service as not running. The
# labels Docker already carries on the running containers are the only
# authoritative answer, so adopt the file list and project name from them.
hikari_adopt_running_stack() {
  if [[ -n "${COMPOSE_FILE:-}" ]]; then
    return 0
  fi

  local container labels project files
  for container in $(docker ps -q 2>/dev/null); do
    labels=$(docker inspect "$container" --format \
      '{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.project.config_files"}}' \
      2>/dev/null) || continue
    project=${labels%%|*}
    files=${labels#*|}
    case "$files" in
      *"$HIKARI_LOCAL_DIR/docker-compose.yml"*)
        export COMPOSE_PROJECT_NAME="$project"
        export COMPOSE_FILE="${files//,/:}"
        return 0
        ;;
    esac
  done

  # Nothing from this checkout is running yet, which is the development case.
  export COMPOSE_FILE="$HIKARI_LOCAL_DIR/docker-compose.yml"
}

# The credentials of an installed stack are generated at install time and live
# nowhere on disk, so an operator verifying production would have to retype
# them. The database container already holds them; reading them there keeps the
# secret out of shell history and out of this repository.
hikari_adopt_database_credentials() {
  local container
  container=$(hikari_compose ps -q db 2>/dev/null | head -1) || true
  if [[ -z "$container" ]]; then
    return 0
  fi

  HIKARI_DB_USER=${HIKARI_DB_USER:-$(hikari_container_env "$container" MARIADB_USER)}
  HIKARI_DB_PASSWORD=${HIKARI_DB_PASSWORD:-$(hikari_container_env "$container" MARIADB_PASSWORD)}
  HIKARI_DB_ROOT_PASSWORD=${HIKARI_DB_ROOT_PASSWORD:-$(hikari_container_env "$container" MARIADB_ROOT_PASSWORD)}
  HIKARI_DB_NAME=${HIKARI_DB_NAME:-$(hikari_container_env "$container" MARIADB_DATABASE)}
}

hikari_adopt_running_stack
hikari_adopt_database_credentials

# An explicit environment value always wins; these are the development defaults
# for a stack that has not been installed.
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
