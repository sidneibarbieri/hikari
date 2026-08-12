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
