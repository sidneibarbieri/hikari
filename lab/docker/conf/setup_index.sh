#!/bin/bash

# Aguardar Elasticsearch estar pronto
until curl -s -u elastic:$ELASTIC_PASSWORD http://elasticsearch:9200/_cluster/health | grep '"status":"green"' > /dev/null; do
  echo "Aguardando Elasticsearch..."
  sleep 5
done

# Criar índice "competition"
curl -X PUT -u elastic:$ELASTIC_PASSWORD "http://elasticsearch:9200/competition" \
-H "Content-Type: application/json" \
-d '{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0
  },
  "mappings": {
    "properties": {
      "team_name": { "type": "text" },
      "score": { "type": "integer" },
      "timestamp": { "type": "date" }
    }
  }
}'

# Inserir dados de exemplo
curl -X POST -u elastic:$ELASTIC_PASSWORD "http://elasticsearch:9200/competition/_doc/" \
-H "Content-Type: application/json" \
-d '{
  "team_name": "Team Alpha",
  "score": 95,
  "timestamp": "2024-11-19T12:00:00"
}'

curl -X POST -u elastic:$ELASTIC_PASSWORD "http://elasticsearch:9200/competition/_doc/" \
-H "Content-Type: application/json" \
-d '{
  "team_name": "Team Beta",
  "score": 88,
  "timestamp": "2024-11-19T13:00:00"
}'

echo "Índice 'competition' criado e populado."
