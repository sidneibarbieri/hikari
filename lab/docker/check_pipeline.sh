#!/bin/bash

echo "Checking Kafka topics..."
docker exec -it docker-kafka-1 kafka-topics.sh --bootstrap-server localhost:9092 --list

echo "Checking Logstash logs for errors..."
docker logs docker-logstash-1 | grep -i error

echo "Checking Elasticsearch indices..."
curl -X GET "http://localhost:9200/_cat/indices?v" -u elastic:adminPass123

echo "Testing search on competition1 index..."
curl -X GET "http://localhost:9200/competition1/_search?size=1&pretty" -u elastic:adminPass123
