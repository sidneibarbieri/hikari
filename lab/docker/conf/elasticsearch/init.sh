#!/bin/bash

echo "Iniciando script de configuração do Elasticsearch..."

# Aguarda até que o Elasticsearch esteja pronto
until curl -s -u elastic:adminPass123 http://localhost:9200/_cluster/health; do
  echo "$(date) - Aguardando Elasticsearch iniciar..."
  sleep 5
done

echo "Elasticsearch está disponível, aplicando configurações..."

# Criação do papel de somente leitura
curl -X PUT "http://localhost:9200/_security/role/kibana_read_only_role" \
  -H "Content-Type: application/json" \
  -u elastic:adminPass123 \
  -d '{
    "cluster": ["monitor"],
    "indices": [{"names": ["*"], "privileges": ["read"]}]
  }'

# Criação do usuário de somente leitura
curl -X POST "http://localhost:9200/_security/user/user" \
  -H "Content-Type: application/json" \
  -u elastic:adminPass123 \
  -d '{"password": "userPass456", "roles": ["kibana_read_only_role"]}'

echo "Configurações aplicadas com sucesso!"

