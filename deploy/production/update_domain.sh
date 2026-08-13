#!/usr/bin/env bash
# Updates the public domain in the deployment configuration.

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Uso: bash update_domain.sh <dominio>" >&2
  exit 2
fi

domain=$1
if [[ ! "$domain" =~ ^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$ ]]; then
  echo "Domínio inválido: $domain" >&2
  exit 2
fi

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
environment_file=${HIKARI_PRODUCTION_ENV:-"$script_dir/.env.production"}

if [[ ! -f "$environment_file" ]]; then
  echo "Arquivo de ambiente de produção não encontrado: $environment_file" >&2
  exit 1
fi

temporary_file=$(mktemp "${environment_file}.XXXXXX")
trap 'rm -f "$temporary_file"' EXIT

awk -v value="$domain" '
  BEGIN { replaced = 0 }
  /^HIKARI_DOMAIN=/ { print "HIKARI_DOMAIN=" value; replaced = 1; next }
  { print }
  END { if (!replaced) print "HIKARI_DOMAIN=" value }
' "$environment_file" > "$temporary_file"

mv "$temporary_file" "$environment_file"
trap - EXIT
echo "HIKARI_DOMAIN atualizado em $environment_file"
