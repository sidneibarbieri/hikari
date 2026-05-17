#!/usr/bin/env bash
# Hikari local bootstrap: take a fresh laptop to a running competition stack
# in one command, with friendly checks at every step.
#
# Aimed at the "tecnico pouco instruido" persona named in the artifact
# brief: someone who knows how to read a terminal but should not have
# to research what Docker is or which command installs it.
#
# What it does, in order:
#   1. Detects the OS (Linux distros / macOS) so messages are accurate.
#   2. Verifies system resources (RAM, disk, free ports).
#   3. Checks Docker + docker compose v2; if missing, prints the exact
#      install command for the detected platform. Root-level package
#      installs stay under operator control.
#   4. Copies .env.example -> .env on first run.
#   5. Builds the stack (docker compose up -d --build).
#   6. Runs run_acceptance.sh and surfaces the green/red summary.
#
# Idempotent: subsequent runs skip what's already done. Reports each
# step with a clear PASS / SKIP / NEEDS-ACTION marker so the operator
# always knows where they are.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

ok()    { printf '  \033[32m✓\033[0m %s\n' "$1"; }
skip()  { printf '  \033[33m·\033[0m %s\n' "$1"; }
fail()  { printf '  \033[31m✗\033[0m %s\n' "$1" >&2; }
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

# Disk — need ~10 GB for images + indices.
disk_free_gb=$(df -BG "$SCRIPT_DIR" | awk 'NR==2 {gsub("G","",$4); print $4}')
if [[ "$disk_free_gb" -ge 10 ]]; then
    ok "Disk: ${disk_free_gb} GB free in $(pwd)"
else
    fail "Disk: only ${disk_free_gb} GB free — Hikari needs at least 10 GB."
    exit 1
fi

# Ports — refuse to start if 8000 (CTFd) or 5601 (Kibana) is busy.
for port in 8000 5601; do
    if (command -v lsof >/dev/null && lsof -nP -iTCP:$port -sTCP:LISTEN >/dev/null 2>&1); then
        fail "Port $port is already in use. Stop the other service and re-run."
        exit 1
    fi
done
ok "Ports 8000 (CTFd) and 5601 (Kibana) are free"


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

if ! docker compose version >/dev/null 2>&1; then
    if ! command -v docker-compose >/dev/null 2>&1; then
        fail 'docker compose v2 not found.'
        cat <<EOF

    Modern Docker Desktop bundles compose; CLI users on Linux can
    install it with:
      sudo apt-get install docker-compose-plugin
EOF
        exit 1
    fi
fi
ok 'docker compose available'


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
# 5. Build and start the stack
# ---------------------------------------------------------------------------

step '5/6 Bringing the stack up (this may take a few minutes on first run)'

docker compose up -d --build


# ---------------------------------------------------------------------------
# 6. Acceptance suite
# ---------------------------------------------------------------------------

step '6/6 Running the acceptance suite'

bash run_acceptance.sh


cat <<EOF

──────────────────────────────────────────────────────────────────────
  Hikari is up.
    CTFd:    http://localhost:8000
    Kibana:  http://localhost:5601
    Login:   admin@hikari.local / hikari_comp@2026  (change before
             exposing any port — see SECURITY.md)
──────────────────────────────────────────────────────────────────────
EOF
