# setup_kibana.sh 
#!/bin/bash
set -e

# === Variáveis de Credenciais ===
ES_USER="elastic"
ES_PASS="adminPass123"

# === Helper Function ===
print_header() {
  echo "===================="
  echo "$1"
  echo "===================="
}

# === Aguardar Serviço ===
wait_for_service() {
  local name=$1
  local url=$2
  print_header "Waiting for $name to be ready"
  until curl -s -u "$ES_USER:$ES_PASS" "$url" >/dev/null; do
    echo "$name ainda não está pronto. Tentando novamente em 5 segundos..."
    sleep 5
  done
  echo "✔ $name está pronto."
}

# === Verificar índice Elasticsearch ===
check_elasticsearch_index() {
  local index="competition1"
  print_header "Checking if Elasticsearch index '$index' exists"
  if curl -s -u "$ES_USER:$ES_PASS" -o /dev/null -w "%{http_code}" "http://localhost:9200/$index" | grep -q "200"; then
    echo "✔ Elasticsearch index '$index' already exists."
  else
    echo "ℹ Elasticsearch index '$index' does not exist. Creating it..."
    create_elasticsearch_index "$index"
  fi
}

# === Criar índice Elasticsearch ===
create_elasticsearch_index() {
  local index="$1"
  print_header "Creating Elasticsearch index '$index'"
  curl -s -X PUT -u "$ES_USER:$ES_PASS" "http://localhost:9200/$index" \
    -H "Content-Type: application/json" \
    -d '{
      "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0
      },
      "mappings": {
        "properties": {
          "@timestamp": { "type": "date" },
          "message": { "type": "text" }
        }
      }
    }'
  echo "✔ Elasticsearch index '$index' created successfully."
}

# === Configurar padrão de índice no Kibana ===
setup_kibana_index() {
  print_header "Setting up Kibana index pattern"
  curl -s -X POST -u "$ES_USER:$ES_PASS" "http://localhost:5601/api/saved_objects/index-pattern" \
    -H "kbn-xsrf: true" \
    -H "Content-Type: application/json" \
    -d '{
      "attributes": {
        "title": "competition1",
        "timeFieldName": "@timestamp"
      }
    }'
  echo "✔ Kibana index pattern for 'competition1' set up successfully."
}

# === Publicar mensagem de teste no Kafka ===
publish_test_message() {
  print_header "Publishing a test message to Kafka"
  docker exec docker-kafka-1 kafka-console-producer.sh \
    --broker-list kafka:9092 \
    --topic competition1 <<EOF
{"@timestamp": "$(date -Is)", "message": "Test message from setup_kibana.sh"}
EOF
  echo "✔ Test message published to 'competition1'."
}

# === Execução Principal ===
wait_for_service "Elasticsearch" "http://localhost:9200"
wait_for_service "Kibana" "http://localhost:5601"

check_elasticsearch_index
setup_kibana_index
publish_test_message

print_header "Setup Complete"
echo "✔ Elasticsearch, Kibana, and Logstash are configured and operational."

