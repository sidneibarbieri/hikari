#!/usr/bin/env bash
# =============================================================================
# Hikari Platform — Script de configuração de produção
# Executa como root em Ubuntu 22.04 / Debian 12.
# Uso: sudo ./setup_production.sh
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✔${NC} $*"; }
info() { echo -e "${BLUE}▶${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
fail() { echo -e "${RED}✖ ERRO:${NC} $*"; exit 1; }

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PLATFORM_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
ENV_FILE="$SCRIPT_DIR/.env.production"

# ---- 1. Verificar pré-requisitos --------------------------------------------
info "Verificando pré-requisitos..."

[[ -f "$ENV_FILE" ]] \
  || fail "Arquivo $ENV_FILE não encontrado. Copie .env.production.example e preencha."

source "$ENV_FILE"

[[ -n "${HIKARI_DOMAIN:-}" ]] || fail "HIKARI_DOMAIN não definido em .env.production"
[[ -n "${ADMIN_PASSWORD:-}" ]] || fail "ADMIN_PASSWORD não definido"
[[ -n "${SECRET_KEY:-}" ]]    || fail "SECRET_KEY não definido"

[[ ${#KIBANA_ENCRYPTION_KEY:-} -eq 32 ]] \
  || fail "KIBANA_ENCRYPTION_KEY deve ter exatamente 32 caracteres"
[[ ${#ES_ENCRYPTION_KEY:-} -eq 32 ]] \
  || fail "ES_ENCRYPTION_KEY deve ter exatamente 32 caracteres"

command -v docker  >/dev/null 2>&1 || fail "Docker não instalado. Siga o Passo 1 do README."
command -v certbot >/dev/null 2>&1 || {
  info "Instalando certbot..."
  apt-get update -qq && apt-get install -y -qq certbot python3-certbot-nginx
}

ok "Pré-requisitos verificados."

# ---- 2. Instalar Nginx ------------------------------------------------------
info "Instalando/configurando Nginx..."
command -v nginx >/dev/null 2>&1 || apt-get install -y -qq nginx

# Desativar o site default para liberar a porta 80
rm -f /etc/nginx/sites-enabled/default

# Criar configuração Nginx para o Hikari
cat > /etc/nginx/sites-available/hikari <<NGINX
# Hikari Platform — Nginx reverse proxy
# Gerado por setup_production.sh em $(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Redirect HTTP → HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name ${HIKARI_DOMAIN};

    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://\$host\$request_uri; }
}

# HTTPS
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

    # Tamanho máximo de upload (logs podem ser grandes)
    client_max_body_size 200M;

    # Proxy para o CTFd
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

ln -sf /etc/nginx/sites-available/hikari /etc/nginx/sites-enabled/hikari
nginx -t || fail "Configuração do Nginx inválida. Verifique /etc/nginx/sites-available/hikari."
ok "Nginx configurado."

# ---- 3. Emitir certificado SSL ----------------------------------------------
info "Verificando certificado SSL para ${HIKARI_DOMAIN}..."
mkdir -p /var/www/certbot
systemctl start nginx

if [[ -f "/etc/letsencrypt/live/${HIKARI_DOMAIN}/fullchain.pem" ]]; then
  ok "Certificado já existe — pulando emissão."
else
  info "Emitindo certificado via Let's Encrypt (gratuito)..."
  certbot certonly --nginx \
    -d "${HIKARI_DOMAIN}" \
    --non-interactive --agree-tos \
    --email "${ADMIN_EMAIL}" \
    --redirect \
    || fail "Falha ao emitir certificado. Verifique se o DNS ${HIKARI_DOMAIN} aponta para este servidor."
  ok "Certificado SSL emitido."
fi

# ---- 4. Renovação automática ------------------------------------------------
info "Configurando renovação automática do certificado..."
CRON_RENEW="0 3 * * * certbot renew --quiet --nginx && systemctl reload nginx"
( crontab -l 2>/dev/null | grep -v certbot; echo "$CRON_RENEW" ) | crontab -
ok "Renovação agendada diariamente às 03:00."

# ---- 5. Construir .env de produção para o Compose ---------------------------
info "Gerando variáveis de ambiente para o Compose..."
COMPOSE_ENV="$SCRIPT_DIR/.compose.env"
cat > "$COMPOSE_ENV" <<ENV
# Gerado por setup_production.sh — não edite manualmente
HIKARI_DOMAIN=${HIKARI_DOMAIN}
SECRET_KEY=${SECRET_KEY}
DATABASE_PASSWORD=${DATABASE_PASSWORD:-hikari_db_pw}
KIBANA_ENCRYPTION_KEY=${KIBANA_ENCRYPTION_KEY}
ES_ENCRYPTION_KEY=${ES_ENCRYPTION_KEY}
HIKARI_GOOGLE_CLIENT_ID=${HIKARI_GOOGLE_CLIENT_ID:-}
HIKARI_GOOGLE_CLIENT_SECRET=${HIKARI_GOOGLE_CLIENT_SECRET:-}
HIKARI_OAUTH_REDIRECT_BASE=https://${HIKARI_DOMAIN}
CTFD_PORT=${CTFD_INTERNAL_PORT:-8000}
ENV
chmod 600 "$COMPOSE_ENV"
ok "Variáveis configuradas."

# ---- 6. Subir os serviços ---------------------------------------------------
info "Subindo serviços Hikari (primeira inicialização pode levar 3-5 min)..."
cd "$SCRIPT_DIR"
docker compose \
  -f docker-compose.production.yml \
  --env-file "$COMPOSE_ENV" \
  up -d --build

# Aguarda CTFd ficar saudável
info "Aguardando CTFd ficar pronto..."
for i in $(seq 1 30); do
  curl -sf "http://localhost:${CTFD_INTERNAL_PORT:-8000}/healthcheck" >/dev/null 2>&1 && break
  sleep 10
  [[ $i -eq 30 ]] && fail "CTFd não ficou pronto em 5 min. Verifique: docker compose logs ctfd"
done
ok "CTFd está rodando."

# ---- 7. Configurar admin e branding -----------------------------------------
info "Configurando administrador e branding..."
cd "$PLATFORM_DIR/deploy/local"
ADMIN_EMAIL="${ADMIN_EMAIL}" ADMIN_PASSWORD="${ADMIN_PASSWORD}" bash ensure_admin.sh
bash apply_theme.sh
bash apply_branding.sh
ok "Admin e branding configurados."

# ---- 8. Importar dashboard SIEM ---------------------------------------------
info "Importando dashboard SIEM..."
bash import_siem_dashboards.sh
ok "Dashboard SIEM importado."

# ---- 9. Recarregar Nginx com SSL -------------------------------------------
systemctl reload nginx
ok "Nginx recarregado com SSL."

# ---- 10. Configurar backup diário ------------------------------------------
info "Configurando backup automático diário..."
BACKUP_SCRIPT="$SCRIPT_DIR/backup.sh"
cat > "$BACKUP_SCRIPT" <<'BACKUP'
#!/usr/bin/env bash
# Backup diário do Hikari
BACKUP_DIR=/opt/hikari/backups
mkdir -p "$BACKUP_DIR"
FILENAME="hikari-$(date +%Y-%m-%d-%H%M).zip"
cd /opt/hikari/hikari-platform/deploy/local && bash import_backup.sh --export "$BACKUP_DIR/$FILENAME"
# Mantém apenas os últimos 7 backups
ls -t "$BACKUP_DIR"/hikari-*.zip | tail -n +8 | xargs -r rm --
echo "Backup criado: $BACKUP_DIR/$FILENAME"
BACKUP
chmod +x "$BACKUP_SCRIPT"
CRON_BACKUP="0 2 * * * $BACKUP_SCRIPT >> /var/log/hikari-backup.log 2>&1"
( crontab -l 2>/dev/null | grep -v hikari-backup; echo "$CRON_BACKUP" ) | crontab -
ok "Backup diário agendado às 02:00 (retenção: 7 dias)."

# ---- Firewall ---------------------------------------------------------------
if command -v ufw >/dev/null 2>&1; then
  info "Configurando firewall (ufw)..."
  ufw allow 22/tcp  comment 'SSH'   >/dev/null 2>&1 || true
  ufw allow 80/tcp  comment 'HTTP'  >/dev/null 2>&1 || true
  ufw allow 443/tcp comment 'HTTPS' >/dev/null 2>&1 || true
  ufw --force enable >/dev/null 2>&1 || true
  ok "Firewall configurado (22/80/443 abertos)."
fi

# ---- Resumo -----------------------------------------------------------------
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Hikari Platform — Instalação concluída com sucesso!   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  URL:   https://${HIKARI_DOMAIN}"
echo "  Admin: ${ADMIN_EMAIL}"
echo ""
echo "  Próximos passos:"
echo "  1. Acesse https://${HIKARI_DOMAIN} e confirme que carrega"
echo "  2. Entre com ${ADMIN_EMAIL} e a senha configurada"
echo "  3. Importe desafios em /admin/hikari → 'Importar instância'"
echo "  4. Configure equipes e inicie a competição em /admin/hikari"
echo ""
echo "  Logs: docker compose -f $SCRIPT_DIR/docker-compose.production.yml logs -f"
echo "  Backup: $BACKUP_SCRIPT"
echo ""
