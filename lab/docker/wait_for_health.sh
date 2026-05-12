#!/bin/bash

set -e

# Lista de serviços a serem verificados
services=("zookeeper" "kafka" "elasticsearch" "logstash" "kibana" "fastapi_app")

# Função para verificar a saúde dos serviços
check_health() {
    for service in "${services[@]}"; do
        status=$(docker inspect --format '{{.State.Health.Status}}' "docker_${service}_1")
        if [ "$status" != "healthy" ]; then
            return 1
        fi
    done
    return 0
}

# Aguarde até que todos os serviços estejam saudáveis
while ! check_health; do
    echo "Aguardando os serviços estarem saudáveis..."
    sleep 10
done

echo "Todos os serviços estão saudáveis!"

