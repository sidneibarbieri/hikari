#!/bin/bash

# Caminho para o script de setup do Elasticsearch
SETUP_ELASTICSEARCH="./scripts/setup_elasticsearch.sh"

# Verifica se o script de setup do Elasticsearch existe
if [ -f "${SETUP_ELASTICSEARCH}" ]; then
  echo "Iniciando a configuração do Elasticsearch, criação de papel e usuários..."
  bash "${SETUP_ELASTICSEARCH}"
else
  echo "Erro: O script ${SETUP_ELASTICSEARCH} não foi encontrado!"
  exit 1
fi

# Configuração adicional do Kibana (se necessário)
echo "✔ Configuração do Kibana concluída."

