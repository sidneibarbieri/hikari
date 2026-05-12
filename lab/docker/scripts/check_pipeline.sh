#!/bin/bash

# Credenciais do Elasticsearch
ES_USER="elastic"
ES_PASS="adminPass123"

# Kafka Configuração
KAFKA_CONTAINER="kafka"
TOPIC="competition1"

# Logstash Configuração
LOGSTASH_CONTAINER="logstash"

# Função para imprimir cabeçalho
print_header() {
  echo "===================="
  echo "$1"
  echo "===================="
}

# Função para verificar tópico do Kafka
check_kafka_topic() {
  print_header "Checking Kafka topics..."
  local kafka_topics=$(docker exec "$KAFKA_CONTAINER" kafka-topics.sh --list --bootstrap-server kafka:9092 2>/dev/null)
  if echo "$kafka_topics" | grep -q "$TOPIC"; then
    echo "✔ Kafka topic '$TOPIC' exists."
  else
    echo "✖ Kafka topic '$TOPIC' does not exist! Action Required: Create the topic using 'kafka-topics.sh'."
    exit 1
  fi
}

# Função para verificar logs do Logstash
check_logstash_logs() {
  print_header "Checking Logstash logs for errors..."
  local logstash_logs=$(docker logs "$LOGSTASH_CONTAINER" 2>&1 | grep -Ei "error|critical|exception|LEADER_NOT_AVAILABLE" | grep -Ev "DEBUG|INFO" | tail -n 5)
  if [ -z "$logstash_logs" ]; then
    echo "✔ No critical errors detected in Logstash logs."
  else
    echo "✖ Critical errors detected in Logstash logs! See below:"
    echo "$logstash_logs"
    if echo "$logstash_logs" | grep -q "LEADER_NOT_AVAILABLE"; then
      echo "✖ Action Required: Kafka topic '$TOPIC' may have leader election issues. Try recreating the topic."
    fi
  fi
}

# Função para verificar índice no Elasticsearch
check_elasticsearch_index() {
  print_header "Checking Elasticsearch indices..."
  if ! curl -s -u "$ES_USER:$ES_PASS" "http://localhost:9200" >/dev/null; then
    echo "✖ Elasticsearch is not accessible! Action Required: Check if the service is running and reachable."
    exit 1
  fi
  local es_indices=$(curl -s -u "$ES_USER:$ES_PASS" -X GET "http://localhost:9200/_cat/indices?v")
  if echo "$es_indices" | grep -q "$TOPIC"; then
    local index_status=$(echo "$es_indices" | grep "$TOPIC" | awk '{print $2}')
    echo "$es_indices" | grep "$TOPIC"
    if [ "$index_status" == "green" ]; then
      echo "✔ Elasticsearch index '$TOPIC' is healthy (status: $index_status)."
    elif [ "$index_status" == "yellow" ]; then
      echo "⚠ Elasticsearch index '$TOPIC' has replication issues (status: $index_status)."
      echo "   Action Required: Check shard allocation and replication settings."
    elif [ "$index_status" == "open" ]; then
      echo "✖ Elasticsearch index '$TOPIC' is open but not ready. Investigate further."
      echo "   Action Required: Check for errors in the Logstash or Elasticsearch logs."
    else
      echo "✖ Elasticsearch index '$TOPIC' has critical issues (status: $index_status)."
      echo "   Action Required: Investigate the issue in Elasticsearch."
    fi
  else
    echo "✖ Elasticsearch index '$TOPIC' not found! Action Required: Check your Logstash pipeline."
    exit 1
  fi
}

# Função para testar busca no índice do Elasticsearch
test_elasticsearch_search() {
  print_header "Testing search on '$TOPIC' index..."
  local search_result=$(curl -s -u "$ES_USER:$ES_PASS" -X GET "http://localhost:9200/$TOPIC/_search?size=1&pretty" | grep '"hits"' -A 3)
  if echo "$search_result" | grep -q '"total" : {'; then
    echo "✔ Data found in '$TOPIC' index."
  else
    echo "✖ No data found in '$TOPIC' index! Action Required: Verify your Logstash pipeline configuration."
  fi
}

# Execução Principal
clear
check_kafka_topic
check_logstash_logs
check_elasticsearch_index
test_elasticsearch_search
print_header "Pipeline check complete!"

