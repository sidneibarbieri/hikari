#!/bin/bash

# Caminho para o script de setup
SETUP_SCRIPT="./scripts/setup_elasticsearch.sh"

# Verifica se o script de setup existe
if [ -f "${SETUP_SCRIPT}" ]; then
  echo "Iniciando a configuração do Elasticsearch, criação de papel e usuários..."
  bash "${SETUP_SCRIPT}"
else
  echo "Erro: O script ${SETUP_SCRIPT} não foi encontrado!"
  exit 1
fi

