#!/bin/bash
set -e

echo "Aguardando Elasticsearch ficar pronto..."
until curl -s -o /dev/null -w "%{http_code}" -X GET "http://elasticsearch:9200" -u elastic:adminPass123 | grep -q "200"; do
  echo "Elasticsearch ainda não está pronto. Tentando novamente em 5 segundos..."
  sleep 5
done

echo "Configurando Elasticsearch..."

# Função para verificar se um recurso já existe
resource_exists() {
  local endpoint=$1
  local name=$2
  curl -s -u elastic:adminPass123 "http://elasticsearch:9200/$endpoint/$name" | grep -q "$name"
}

# Criar role de leitura
if resource_exists "_security/role" "kibana_read_only_role"; then
  echo "Role 'kibana_read_only_role' já existe. Pulando criação..."
else
  echo "Criando role 'kibana_read_only_role'..."
  curl -X PUT -u elastic:adminPass123 "http://elasticsearch:9200/_security/role/kibana_read_only_role" \
  -H "Content-Type: application/json" \
  -d '{
    "cluster": ["monitor"],
    "indices": [
      {
        "names": ["*"],
        "privileges": ["read", "view_index_metadata"]
      }
    ]
  }'
fi

# Criar usuário de leitura
if resource_exists "_security/user" "kibana_read_only_user"; then
  echo "Usuário 'kibana_read_only_user' já existe. Pulando criação..."
else
  echo "Criando usuário 'kibana_read_only_user'..."
  curl -X PUT -u elastic:adminPass123 "http://elasticsearch:9200/_security/user/kibana_read_only_user" \
  -H "Content-Type: application/json" \
  -d '{
    "password": "readOnlyPass123",
    "roles": ["kibana_read_only_role"]
  }'
fi

# Criar índice competition1
if curl -s -u elastic:adminPass123 "http://elasticsearch:9200/_cat/indices/competition1" | grep -q "competition1"; then
  echo "Índice 'competition1' já existe. Pulando criação..."
else
  echo "Criando índice 'competition1'..."
  curl -X PUT -u elastic:adminPass123 "http://elasticsearch:9200/competition1" \
  -H 'Content-Type: application/json' \
  -d '{
    "mappings": {
      "properties": {
        "timestamp": { "type": "date" },
        "message": { "type": "text" },
        "level": { "type": "keyword" }
      }
    }
  }'
fi

echo "Configuração concluída com sucesso!"

