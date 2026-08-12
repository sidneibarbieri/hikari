#!/usr/bin/env bash
# Starts the local operator stack after checking host prerequisites.
# The acceptance suite runs in a separate disposable Compose project.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"
source "$SCRIPT_DIR/lib/compose.sh"

ok()    { printf '  \033[32m[ok]\033[0m %s\n' "$1"; }
skip()  { printf '  \033[33m[skip]\033[0m %s\n' "$1"; }
fail()  { printf '  \033[31m[error]\033[0m %s\n' "$1" >&2; }
step()  { printf '\n\033[1m%s\033[0m\n' "$1"; }


# ---------------------------------------------------------------------------
# 1. Detect OS
# ---------------------------------------------------------------------------

step '1/6 Detecting environment'

uname_s=$(uname -s)
case "$uname_s" in
    Linux)
        os_family=linux
        os_distro=$(. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME:-Linux}")
        ;;
    Darwin)
        os_family=macos
        os_distro="macOS $(sw_vers -productVersion 2>/dev/null || echo)"
        ;;
    *)
        fail "Unsupported OS: $uname_s. Hikari runs on Linux or macOS."
        exit 1
        ;;
esac
ok "OS: $os_distro"


# ---------------------------------------------------------------------------
# 2. Resource sanity (RAM, disk, ports)
# ---------------------------------------------------------------------------

step '2/6 Checking system resources'

# RAM — Elasticsearch alone needs ~2 GB, we target 8 GB total for comfort.
case "$os_family" in
    linux)
        total_ram_mb=$(awk '/MemTotal/ {print int($2 / 1024)}' /proc/meminfo)
        ;;
    macos)
        total_ram_mb=$(($(sysctl -n hw.memsize) / 1024 / 1024))
        ;;
esac
if [[ "$total_ram_mb" -ge 7600 ]]; then
    ok "RAM: ${total_ram_mb} MB (≥ 8 GB recommended)"
else
    skip "RAM: ${total_ram_mb} MB (8 GB recommended; smaller machines may run, slowly)"
fi

# Disk — use KiB so this works on GNU and BSD df implementations.
disk_free_gb=$(df -k "$SCRIPT_DIR" | awk 'NR==2 {print int($4 / 1024 / 1024)}')
if [[ "$disk_free_gb" -ge 10 ]]; then
    ok "Disk: ${disk_free_gb} GB free in $(pwd)"
else
    fail "Disk: only ${disk_free_gb} GB free — Hikari needs at least 10 GB."
    exit 1
fi

# Only CTFd is published locally. Kibana stays behind the authenticated proxy.
ctfd_port=${CTFD_PORT:-8000}
if command -v lsof >/dev/null && lsof -nP -iTCP:"$ctfd_port" -sTCP:LISTEN >/dev/null 2>&1; then
    if hikari_compose ps --services --status running 2>/dev/null | grep -qx 'ctfd'; then
        skip "Port $ctfd_port is already used by the local Hikari stack"
    else
        fail "Port $ctfd_port is already in use. Stop the other service and re-run."
        exit 1
    fi
else
    ok "Port $ctfd_port (CTFd) is free"
fi


# ---------------------------------------------------------------------------
# 3. Docker + docker compose
# ---------------------------------------------------------------------------

step '3/6 Checking Docker'

if ! command -v docker >/dev/null 2>&1; then
    fail 'Docker is not installed.'
    cat <<EOF

    On $os_distro, install Docker with:
EOF
    case "$os_family" in
        linux) printf "      curl -fsSL https://get.docker.com | sh\n" ;;
        macos) printf "      brew install --cask docker\n" ;;
    esac
    cat <<EOF

    Then add your user to the docker group (Linux):
      sudo usermod -aG docker \$USER && newgrp docker

    Re-run this script after Docker is installed.
EOF
    exit 1
fi
ok "Docker: $(docker --version)"

if ! command -v docker-compose >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then
        fail 'Docker Compose not found.'
        cat <<EOF

    Install either Docker Compose v2 or the docker-compose command:
      sudo apt-get install docker-compose-plugin
EOF
        exit 1
fi
ok 'Docker Compose available'


# ---------------------------------------------------------------------------
# 4. .env file
# ---------------------------------------------------------------------------

step '4/6 Preparing environment file'

if [[ -f .env ]]; then
    skip ".env already exists (kept as-is; delete to regenerate)"
else
    cp .env.example .env
    ok 'Copied .env.example -> .env'
fi


# ---------------------------------------------------------------------------
# 5. Acceptance suite
# ---------------------------------------------------------------------------

step '5/6 Running the isolated acceptance suite'

bash tests/acceptance_isolated.sh


# ---------------------------------------------------------------------------
# 6. Build and start the stack
# ---------------------------------------------------------------------------

step '6/6 Bringing the stack up (this may take a few minutes on first run)'

hikari_compose up -d --build


cat <<EOF

Hikari is up.
  CTFd:  http://localhost:${ctfd_port}
  SIEM:  http://localhost:${ctfd_port}/hikari/siem
  Login: admin@hikari.local / hikari_comp@2026

Change the administrator password before exposing the service. See SECURITY.md.
EOF
