#!/bin/bash

# Aguarda o Elasticsearch ficar disponível
until curl -u elastic:$ELASTIC_PASSWORD -s "http://elasticsearch:9200" > /dev/null; do
  echo "Aguardando Elasticsearch ficar disponível..."
  sleep 5
done

# Criação de usuário
curl -X PUT "http://elasticsearch:9200/_security/user/user" \
  -H "Content-Type: application/json" \
  -u elastic:$ELASTIC_PASSWORD \
  -d '{
    "password" : "'$USER_PASSWORD'",
    "roles" : [ "kibana_read_only" ],
    "full_name" : "Read Only User",
    "email" : "user@example.com"
  }'

