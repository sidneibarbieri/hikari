#!/usr/bin/env bash
# =============================================================================
# Hikari Platform — Script de configuração de produção
# Executa como root em Ubuntu 22.04 / Debian 12.
# Uso: sudo ./setup_production.sh
# =============================================================================
set -euo pipefail

ok()   { printf '[ok] %s\n' "$*"; }
info() { printf '[info] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*"; }
fail() { printf '[error] %s\n' "$*" >&2; exit 1; }

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PLATFORM_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
BASE_COMPOSE_FILE="$PLATFORM_DIR/deploy/local/docker-compose.yml"
ENV_FILE=${HIKARI_PRODUCTION_ENV:-"$SCRIPT_DIR/.env.production"}
COMPOSE_PROJECT_NAME=${HIKARI_COMPOSE_PROJECT:-hikari}
HIKARI_BACKUP_DIR=${HIKARI_BACKUP_DIR:-/opt/hikari/backups}
HIKARI_SKIP_TLS=${HIKARI_SKIP_TLS:-false}

# ---- 1. Verificar pré-requisitos --------------------------------------------
info "Verificando pré-requisitos..."

[[ $EUID -eq 0 ]] || fail "Execute com sudo: sudo bash setup_production.sh"
[[ -f "$ENV_FILE" ]] \
  || fail "Arquivo $ENV_FILE não encontrado. Copie .env.production.example e preencha."

source "$ENV_FILE"

# The deployment file may select a project and backup location without relying
# on environment inherited by sudo.
COMPOSE_PROJECT_NAME=${HIKARI_COMPOSE_PROJECT:-"$COMPOSE_PROJECT_NAME"}
HIKARI_BACKUP_DIR=${HIKARI_BACKUP_DIR:-/opt/hikari/backups}
HIKARI_SKIP_TLS=${HIKARI_SKIP_TLS:-"$HIKARI_SKIP_TLS"}

[[ -n "${HIKARI_DOMAIN:-}" ]] || fail "HIKARI_DOMAIN não definido em $ENV_FILE"
[[ "$HIKARI_DOMAIN" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$ ]] \
  || fail "HIKARI_DOMAIN deve ser um domínio válido, sem protocolo ou caminho."
[[ -n "${ADMIN_EMAIL:-}" ]] || fail "ADMIN_EMAIL não definido"
[[ -n "${ADMIN_PASSWORD:-}" ]] || fail "ADMIN_PASSWORD não definido"
[[ -n "${SECRET_KEY:-}" ]]    || fail "SECRET_KEY não definido"
[[ -n "${DATABASE_PASSWORD:-}" ]] || fail "DATABASE_PASSWORD não definido"
[[ "$DATABASE_PASSWORD" =~ ^[A-Za-z0-9._~-]+$ ]] \
  || fail "DATABASE_PASSWORD deve usar somente letras, números, ponto, sublinhado, hífen ou til."

[[ -n "${KIBANA_ENCRYPTION_KEY:-}" && ${#KIBANA_ENCRYPTION_KEY} -eq 32 ]] \
  || fail "KIBANA_ENCRYPTION_KEY deve ter exatamente 32 caracteres"
[[ -n "${ES_ENCRYPTION_KEY:-}" && ${#ES_ENCRYPTION_KEY} -eq 32 ]] \
  || fail "ES_ENCRYPTION_KEY deve ter exatamente 32 caracteres"

command -v docker  >/dev/null 2>&1 || fail "Docker não instalado. Siga o Passo 1 do README."
if ! command -v docker-compose >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then
  fail "Docker Compose não instalado. Siga o Passo 1 do README."
fi
command -v curl >/dev/null 2>&1 || fail "curl não instalado."
if [[ "$HIKARI_SKIP_TLS" != "true" ]]; then
  command -v certbot >/dev/null 2>&1 || {
    info "Instalando certbot..."
    apt-get update -qq && apt-get install -y -qq certbot python3-certbot-nginx
  }
fi
command -v crontab >/dev/null 2>&1 || {
  info "Instalando serviço de agendamento..."
  apt-get update -qq && apt-get install -y -qq cron
}
systemctl enable --now cron

ok "Pré-requisitos verificados."

# ---- 2. Instalar Nginx ------------------------------------------------------
if [[ "$HIKARI_SKIP_TLS" != "true" ]]; then
info "Instalando/configurando Nginx..."
command -v nginx >/dev/null 2>&1 || apt-get install -y -qq nginx

# Preserve os sites existentes. O bloco com server_name específico abaixo pode
# compartilhar as portas 80 e 443 com o site default do Nginx.

# A configuração inicial usa apenas HTTP. Um host novo ainda não tem os
# arquivos do certificado; testar uma configuração TLS antes da emissão falha.
write_http_nginx_config() {
  cat > /etc/nginx/sites-available/hikari <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${HIKARI_DOMAIN};

    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / {
        proxy_pass         http://127.0.0.1:${CTFD_INTERNAL_PORT:-8000};
        proxy_http_version 1.1;
        proxy_set_header   Upgrade \$http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
NGINX
}

write_https_nginx_config() {
  cat > /etc/nginx/sites-available/hikari <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${HIKARI_DOMAIN};

    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://\$host\$request_uri; }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${HIKARI_DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${HIKARI_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${HIKARI_DOMAIN}/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    client_max_body_size 200M;

    location / {
        proxy_pass         http://127.0.0.1:${CTFD_INTERNAL_PORT:-8000};
        proxy_http_version 1.1;
        proxy_set_header   Upgrade \$http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
NGINX
}

mkdir -p /var/www/certbot
write_http_nginx_config
ln -sf /etc/nginx/sites-available/hikari /etc/nginx/sites-enabled/hikari
nginx -t || fail "Configuração HTTP do Nginx inválida. Verifique /etc/nginx/sites-available/hikari."
systemctl enable --now nginx
ok "Nginx configurado para a emissão do certificado."

# ---- 3. Emitir certificado SSL ----------------------------------------------
info "Verificando certificado SSL para ${HIKARI_DOMAIN}..."

if [[ -f "/etc/letsencrypt/live/${HIKARI_DOMAIN}/fullchain.pem" ]]; then
  ok "Certificado já existe — pulando emissão."
else
  info "Emitindo certificado via Let's Encrypt (gratuito)..."
  certbot certonly --nginx \
    -d "${HIKARI_DOMAIN}" \
    --non-interactive --agree-tos \
    --email "${ADMIN_EMAIL}" \
    || fail "Falha ao emitir certificado. Verifique se o DNS ${HIKARI_DOMAIN} aponta para este servidor."
  ok "Certificado SSL emitido."
fi

write_https_nginx_config
nginx -t || fail "Configuração HTTPS do Nginx inválida. Verifique /etc/nginx/sites-available/hikari."
systemctl reload nginx
ok "Nginx configurado com TLS."

# ---- 4. Renovação automática ------------------------------------------------
info "Configurando renovação automática do certificado..."
CRON_RENEW="0 3 * * * certbot renew --quiet --nginx && systemctl reload nginx"
( crontab -l 2>/dev/null | grep -v certbot; echo "$CRON_RENEW" ) | crontab -
ok "Renovação agendada diariamente às 03:00."
else
  info "TLS adiado: a plataforma será preparada apenas em localhost."
fi

# ---- 5. Construir .env de produção para o Compose ---------------------------
info "Gerando variáveis de ambiente para o Compose..."
COMPOSE_ENV="$SCRIPT_DIR/.compose.env"
cat > "$COMPOSE_ENV" <<ENV
# Gerado por setup_production.sh — não edite manualmente
HIKARI_DOMAIN=${HIKARI_DOMAIN}
SECRET_KEY=${SECRET_KEY}
DATABASE_PASSWORD=${DATABASE_PASSWORD}
KIBANA_ENCRYPTION_KEY=${KIBANA_ENCRYPTION_KEY}
ES_ENCRYPTION_KEY=${ES_ENCRYPTION_KEY}
HIKARI_GOOGLE_CLIENT_ID=${HIKARI_GOOGLE_CLIENT_ID:-}
HIKARI_GOOGLE_CLIENT_SECRET=${HIKARI_GOOGLE_CLIENT_SECRET:-}
HIKARI_OAUTH_REDIRECT_BASE=https://${HIKARI_DOMAIN}
MAILFROM_ADDR=${MAILFROM_ADDR:-noreply@${HIKARI_DOMAIN}}
MAIL_SERVER=${MAIL_SERVER:-}
MAIL_PORT=${MAIL_PORT:-}
MAIL_USEAUTH=${MAIL_USEAUTH:-false}
MAIL_USERNAME=${MAIL_USERNAME:-}
MAIL_PASSWORD=${MAIL_PASSWORD:-}
MAIL_TLS=${MAIL_TLS:-false}
MAIL_SSL=${MAIL_SSL:-false}
CTFD_PORT=${CTFD_INTERNAL_PORT:-8000}
CTFD_WORKERS=${CTFD_WORKERS:-4}
HIKARI_BACKUP_DIR=${HIKARI_BACKUP_DIR}
COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME}
RETENTION_DAYS=${RETENTION_DAYS:-14}
ES_JAVA_OPTS="${ES_JAVA_OPTS:-"-Xms1g -Xmx1g"}"
LS_JAVA_OPTS="${LS_JAVA_OPTS:-"-Xms512m -Xmx512m"}"
KAFKA_HEAP_OPTS="${KAFKA_HEAP_OPTS:-"-Xms512m -Xmx512m"}"
ENV
chmod 600 "$COMPOSE_ENV"
ok "Variáveis configuradas."

mkdir -p "$HIKARI_BACKUP_DIR/elasticsearch"
chown -R 1000:0 "$HIKARI_BACKUP_DIR/elasticsearch"

# ---- 6. Subir os serviços ---------------------------------------------------
info "Subindo serviços Hikari (primeira inicialização pode levar 3-5 min)..."
cd "$SCRIPT_DIR"
source "$PLATFORM_DIR/deploy/local/lib/compose.sh"
hikari_compose \
  -f "$BASE_COMPOSE_FILE" \
  -f docker-compose.production.yml \
  --env-file "$COMPOSE_ENV" \
  -p "$COMPOSE_PROJECT_NAME" \
  up -d --build

# Aguarda CTFd ficar saudável
info "Aguardando CTFd ficar pronto..."
for i in $(seq 1 30); do
  curl -sf "http://localhost:${CTFD_INTERNAL_PORT:-8000}/healthcheck" >/dev/null 2>&1 && break
  sleep 10
  [[ $i -eq 30 ]] && fail "CTFd não ficou pronto em 5 min. Verifique os logs do serviço ctfd."
done
ok "CTFd está rodando."

# ---- 7. Configurar a instância, o administrador e a identidade visual -------
info "Concluindo a configuração inicial e aplicando a identidade visual..."
cd "$PLATFORM_DIR/deploy/local"
export COMPOSE_PROJECT_NAME
export COMPOSE_FILE="$SCRIPT_DIR/docker-compose.production.yml"
export HIKARI_COMPOSE_BASE_FILE="$BASE_COMPOSE_FILE"
export CTFD_URL="http://localhost:${CTFD_INTERNAL_PORT:-8000}"
ADMIN_EMAIL="${ADMIN_EMAIL}" ADMIN_PASSWORD="${ADMIN_PASSWORD}" bash scripts/setup_ctfd.sh
ADMIN_EMAIL="${ADMIN_EMAIL}" ADMIN_PASSWORD="${ADMIN_PASSWORD}" bash scripts/ensure_admin.sh
bash scripts/apply_theme.sh
bash scripts/apply_branding.sh
ok "Instância, administrador e identidade visual configurados."

# ---- 8. Importar dashboard SIEM ---------------------------------------------
info "Importando dashboard SIEM..."
bash scripts/configure_siem.sh
bash scripts/import_siem_dashboards.sh
ok "Dashboard SIEM importado."

# ---- 9. Recarregar Nginx com SSL -------------------------------------------
if [[ "$HIKARI_SKIP_TLS" != "true" ]]; then
  systemctl reload nginx
  ok "Nginx recarregado com SSL."
fi

# ---- 10. Configurar backup diário ------------------------------------------
info "Configurando backup automático diário..."
BACKUP_SCRIPT="$SCRIPT_DIR/backup.sh"
chmod +x "$BACKUP_SCRIPT"
chmod +x "$SCRIPT_DIR/restore.sh"
CRON_BACKUP="0 2 * * * $BACKUP_SCRIPT >> /var/log/hikari-backup.log 2>&1"
( crontab -l 2>/dev/null | grep -v hikari-backup; echo "$CRON_BACKUP" ) | crontab -
ok "Backup diário agendado às 02:00 (retenção: ${RETENTION_DAYS:-14} dias)."

# ---- Firewall ---------------------------------------------------------------
# Firewalls em nuvem e hosts já estabelecidos podem pertencer à infraestrutura.
# Altere UFW somente quando o operador optar explicitamente por isso.
if [[ "$HIKARI_SKIP_TLS" != "true" && "${HIKARI_MANAGE_UFW:-false}" == "true" ]] && command -v ufw >/dev/null 2>&1; then
  info "Configurando firewall (ufw)..."
  ufw allow 22/tcp  comment 'SSH'   >/dev/null || fail "Não foi possível liberar SSH no firewall."
  ufw allow 80/tcp  comment 'HTTP'  >/dev/null || fail "Não foi possível liberar HTTP no firewall."
  ufw allow 443/tcp comment 'HTTPS' >/dev/null || fail "Não foi possível liberar HTTPS no firewall."
  ufw --force enable >/dev/null || fail "Não foi possível ativar o firewall."
  ok "Firewall configurado (22/80/443 abertos)."
elif [[ "$HIKARI_SKIP_TLS" != "true" ]]; then
  info "Firewall do host preservado; valide as portas 22, 80 e 443 no provedor ou com a equipe de infraestrutura."
fi

# ---- Resumo -----------------------------------------------------------------
printf '\nInstalação concluída.\n'
if [[ "$HIKARI_SKIP_TLS" == "true" ]]; then
  printf 'Acesso temporário: ssh -L 8000:127.0.0.1:%s USUARIO@SERVIDOR\n' "${CTFD_INTERNAL_PORT:-8000}"
  printf 'Depois acesse: http://localhost:8000\n'
  printf 'Para publicar, configure o DNS e execute novamente sem HIKARI_SKIP_TLS=true.\n'
else
  printf 'URL: https://%s\n' "$HIKARI_DOMAIN"
fi
printf 'Administrador: %s\n' "$ADMIN_EMAIL"
printf 'Logs: docker compose -p %s -f %s -f %s/docker-compose.production.yml logs -f\n' \
  "$COMPOSE_PROJECT_NAME" "$BASE_COMPOSE_FILE" "$SCRIPT_DIR"
printf 'Backup: %s\n' "$BACKUP_SCRIPT"
