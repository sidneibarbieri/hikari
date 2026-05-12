#!/bin/bash

set -e

# Senha do usuário admin definida no ambiente
ELASTIC_PASSWORD=${ELASTIC_PASSWORD:-"adminPass123"}
KIBANA_USER="user"
KIBANA_PASSWORD="userPass456"

# Espera até que o Elasticsearch esteja disponível
echo "Aguardando Elasticsearch inicializar..."
until curl -u elastic:$ELASTIC_PASSWORD -s http://localhost:9200/_cluster/health | grep -q "green"; do
  sleep 10
done

echo "Elasticsearch está pronto. Criando usuários..."

# Criação de um usuário somente leitura para o Kibana
curl -X POST -u elastic:$ELASTIC_PASSWORD -H "Content-Type: application/json" http://localhost:9200/_security/user/$KIBANA_USER -d '{
  "password": "'"$KIBANA_PASSWORD"'",
  "roles": ["kibana_dashboard_only"],
  "full_name": "Kibana Read-Only User"
}'

echo "Usuário somente leitura criado com sucesso!"
