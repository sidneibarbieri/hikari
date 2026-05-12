#!/bin/bash
set -e

# === Helper Function ===
print_header() {
  echo "===================="
  echo "$1"
  echo "===================="
}

# === Limpar Ambiente ===
clean_environment() {
  print_header "Stopping and removing all containers, volumes, and orphans"
  docker-compose down --volumes --remove-orphans
}

# === Reiniciar e Iniciar Ambiente ===
start_environment() {
  print_header "Rebuilding and starting Docker environment"
  docker-compose up -d --build
  echo "✔ Docker environment started successfully."
  echo "Waiting for services to stabilize..."
  sleep 30
}

# === Execução Principal ===
print_header "Managing Docker Environment"

clean_environment
start_environment

print_header "Environment is ready"
echo "✔ Use './scripts/setup_kibana.sh' to configure Elasticsearch and Kibana."

