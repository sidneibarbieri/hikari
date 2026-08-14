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

step '1/7 Verificando o ambiente'

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
        fail "Sistema operacional não suportado: $uname_s. O Hikari requer Linux ou macOS."
        exit 1
        ;;
esac
ok "Sistema operacional: $os_distro"


# ---------------------------------------------------------------------------
# 2. Resource sanity (RAM, disk, ports)
# ---------------------------------------------------------------------------

step '2/7 Verificando recursos do sistema'

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
    ok "Memória: ${total_ram_mb} MB (8 GB recomendados)"
else
    skip "Memória: ${total_ram_mb} MB (8 GB recomendados; máquinas menores podem ficar lentas)"
fi

# Disk — use KiB so this works on GNU and BSD df implementations.
disk_free_gb=$(df -k "$SCRIPT_DIR" | awk 'NR==2 {print int($4 / 1024 / 1024)}')
if [[ "$disk_free_gb" -ge 10 ]]; then
    ok "Disco: ${disk_free_gb} GB livres em $(pwd)"
else
    fail "Disco: apenas ${disk_free_gb} GB livres. O Hikari requer pelo menos 10 GB."
    exit 1
fi

# Only CTFd is published locally. Kibana stays behind the authenticated proxy.
ctfd_port=${CTFD_PORT:-8000}
if command -v lsof >/dev/null && lsof -nP -iTCP:"$ctfd_port" -sTCP:LISTEN >/dev/null 2>&1; then
    if hikari_compose ps --services --status running 2>/dev/null | grep -qx 'ctfd'; then
        skip "A porta $ctfd_port já é usada pelo Hikari local"
    else
        fail "A porta $ctfd_port já está em uso. Pare o outro serviço e execute novamente."
        exit 1
    fi
else
    ok "Porta $ctfd_port (CTFd) disponível"
fi


# ---------------------------------------------------------------------------
# 3. Docker + docker compose
# ---------------------------------------------------------------------------

step '3/7 Verificando Docker'

if ! command -v docker >/dev/null 2>&1; then
    fail 'Docker não está instalado.'
    cat <<EOF

    Instale o Docker em $os_distro com:
EOF
    case "$os_family" in
        linux) printf "      curl -fsSL https://get.docker.com | sh\n" ;;
        macos) printf "      brew install --cask docker\n" ;;
    esac
    cat <<EOF

    No Linux, adicione seu usuário ao grupo docker:
      sudo usermod -aG docker \$USER && newgrp docker

    Execute este script novamente após a instalação.
EOF
    exit 1
fi
ok "Docker: $(docker --version)"

if ! command -v docker-compose >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then
        fail 'Docker Compose não foi encontrado.'
        cat <<EOF

    Instale o Docker Compose v2 ou o comando docker-compose:
      sudo apt-get install docker-compose-plugin
EOF
        exit 1
fi
ok 'Docker Compose disponível'


# ---------------------------------------------------------------------------
# 4. .env file
# ---------------------------------------------------------------------------

step '4/7 Preparando o arquivo de ambiente'

if [[ -f .env ]]; then
    skip '.env já existe e foi preservado'
else
    cp .env.example .env
    ok 'Arquivo .env.example copiado para .env'
fi


# ---------------------------------------------------------------------------
# 5. Acceptance suite
# ---------------------------------------------------------------------------

step '5/7 Executando a suíte isolada de aceitação'

bash tests/acceptance_isolated.sh


# ---------------------------------------------------------------------------
# 6. Build and start the stack
# ---------------------------------------------------------------------------

step '6/7 Iniciando a plataforma (a primeira execução pode levar alguns minutos)'

hikari_compose up -d --build
CTFD_URL="http://localhost:${ctfd_port}" bash tests/smoke.sh --wait


# ---------------------------------------------------------------------------
# 7. Configure the operator stack itself
# ---------------------------------------------------------------------------

step '7/7 Configurando a instância Hikari'

CTFD_URL="http://localhost:${ctfd_port}" bash scripts/setup_ctfd.sh
ADMIN_PASSWORD="${ADMIN_PASSWORD:-hikari_comp@2026}" bash scripts/ensure_admin.sh
CTFD_URL="http://localhost:${ctfd_port}" \
  ADMIN_PASSWORD="${ADMIN_PASSWORD:-hikari_comp@2026}" \
  bash scripts/apply_theme.sh
CTFD_URL="http://localhost:${ctfd_port}" \
  ADMIN_PASSWORD="${ADMIN_PASSWORD:-hikari_comp@2026}" \
  bash scripts/apply_branding.sh
bash scripts/configure_siem.sh
bash scripts/import_siem_dashboards.sh


cat <<EOF

Hikari está disponível.
  CTFd:  http://localhost:${ctfd_port}
  SIEM:  http://localhost:${ctfd_port}/hikari/siem
  Login: admin ou admin@hikari.local / hikari_comp@2026

Change the administrator password before exposing the service. See SECURITY.md.
EOF
