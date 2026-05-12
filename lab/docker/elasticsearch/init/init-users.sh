#!/bin/bash

# Criar usuário somente leitura
curl -X POST "http://localhost:9200/_security/user/user" \
     -u elastic:adminPass123 \
     -H "Content-Type: application/json" \
     -d '{
  "password": "userPass456",
  "roles": ["read-only"],
  "full_name": "Read Only User"
}'

# Criar role somente leitura
curl -X POST "http://localhost:9200/_security/role/read-only" \
     -u elastic:adminPass123 \
     -H "Content-Type: application/json" \
     -d '{
  "cluster": ["monitor"],
  "indices": [
    {
      "names": ["*"],
      "privileges": ["read"]
    }
  ]
}'

