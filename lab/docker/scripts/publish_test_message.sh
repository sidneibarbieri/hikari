#!/bin/bash

# Publish a test message to Kafka
echo "Publishing test message to Kafka topic 'competition1'..."
docker exec docker-kafka-1 kafka-console-producer.sh \
  --broker-list kafka:9092 \
  --topic competition1 <<EOF
{"@timestamp": "$(date -Is)", "message": "test message from setup script"}
EOF
echo "✔ Test message published to 'competition1'."

