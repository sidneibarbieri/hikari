### Guia de Uso e Integração do Backend com o Frontend

## Estrutura do Projeto

**Diretórios e Arquivos Importantes:**

- app/: Contém o código da aplicação FastAPI, os testes e o Dockerfile.
  - `Dockerfile`: Define a imagem Docker para a aplicação FastAPI.
  - `dummy_module.py`: Módulo de exemplo para testes.
  - `example.json`: Exemplo de arquivo JSON para upload.
  - `logging_config.yaml`: Configuração de logging.
  - `main.py`: Código principal da aplicação FastAPI.
  - `pytest.ini`: Configuração do pytest.
  - `requirements.txt`: Dependências do projeto.
  - `test_app.py`: Testes para a aplicação FastAPI.
  - `teste_evento.json`: Exemplo de evento JSON.
  - `test.json`: Exemplo de arquivo JSON.
  - `test_minimal.py`: Testes mínimos de exemplo.
- docker/: Contém a configuração do Docker Compose e outros scripts relacionados.
  - `docker-compose.yml`: Configuração do Docker Compose para todos os serviços.
  - `wait_for_health.sh`: Script para verificar a saúde dos serviços.

## Passos para Configuração e Execução

### 1. Clonagem do Repositório

Primeiro, clone o repositório contendo o backend:

```
git clone <URL-DO-SEU-REPOSITORIO>
cd lab
```

### 2. Build e Início dos Serviços com Docker Compose

Navegue até o diretório `docker` e execute o Docker Compose para construir e iniciar todos os serviços necessários (Zookeeper, Kafka, Elasticsearch, Logstash, Kibana, e FastAPI).

```
cd docker
docker-compose up --build
```

### 3. Verificação da Saúde dos Serviços

Use o script `wait_for_health.sh` para garantir que todos os serviços estejam saudáveis antes de prosseguir.

```
bash wait_for_health.sh
```

### 4. Testando o Backend

Para garantir que tudo está funcionando corretamente, navegue até o diretório `app` e execute os testes com pytest.

```
cd ../app
pytest -v --tb=short test_app.py
```

## Utilização dos Endpoints

Os endpoints principais da aplicação FastAPI são:

### GET /

Endpoint raiz que retorna uma mensagem de boas-vindas.

```
curl -X GET "http://localhost:8000/"
```

### GET /run_scenario/

Endpoint para iniciar a simulação de cenário.

```
curl -X GET "http://localhost:8000/run_scenario/"
```

### POST /upload_file/

Endpoint para upload de arquivo JSON.

```
curl -X POST "http://localhost:8000/upload_file/" -F "file=@example.json"
```

### Exemplo de Arquivo JSON

Aqui está um exemplo de arquivo JSON (`example.json`) que pode ser usado para testar o upload:

```
[
    {"key1": "value1"},
    {"key2": "value2"}
]
```

## Estrutura do Projeto Final

Aqui está a estrutura final do projeto:

```
lab/
├── app/
│   ├── Dockerfile
│   ├── dummy_module.py
│   ├── example.json
│   ├── logging_config.yaml
│   ├── main.py
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── test_app.py
│   ├── teste_evento.json
│   └── test_minimal.py
├── docker/
│   ├── docker-compose.yml
│   ├── logstash/
│   ├── test.json
│   └── wait_for_health.sh
└── venv/
```

### Detalhes Adicionais

#### Dockerfile

O Dockerfile define uma imagem baseada no Python 3.9 slim e instala todas as dependências necessárias. Ao construir a imagem Docker, o comando `uvicorn` é utilizado para iniciar o servidor FastAPI.

```
# Usa uma imagem oficial Python 3.9 Slim como imagem de base.
FROM python:3.9-slim

# Define o diretório de trabalho no container.
WORKDIR /app

# Instala as dependências necessárias, incluindo curl.
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de dependências primeiro, para aproveitar o cache do Docker.
COPY requirements.txt .

# Instala as dependências do projeto.
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante dos arquivos do projeto para o diretório de trabalho.
COPY . .

# Comando para executar a aplicação usando Uvicorn.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### docker-compose.yml

O arquivo `docker-compose.yml` configura os serviços necessários: Zookeeper, Kafka, Elasticsearch, Logstash, Kibana, e a aplicação FastAPI. Cada serviço é configurado com verificações de saúde para garantir que todos os componentes estejam funcionando corretamente antes de iniciar as dependências.

```
version: '3.7'

services:
  zookeeper:
    image: bitnami/zookeeper:3.7.0
    ports:
      - "2181:2181"
    networks:
      - hikari
    environment:
      - ALLOW_ANONYMOUS_LOGIN=yes
    healthcheck:
      test: ["CMD", "echo", "ruok", "|", "nc", "localhost", "2181", "|", "grep", "imok"]
      interval: 10s
      timeout: 5s
      retries: 5

  kafka:
    image: wurstmeister/kafka:2.13-2.8.1
    ports:
      - "9092:9092"
    environment:
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT
      KAFKA_LISTENERS: PLAINTEXT://:9092
      KAFKA_DELETE_TOPIC_ENABLE: "true"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      zookeeper:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null"]
      interval: 30s
      timeout: 10s
      retries: 5
    networks:
      - hikari

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.10.2
    environment:
      - discovery.type=single-node
    ports:
      - "9200:9200"
      - "9300:9300"
    networks:
      - hikari
    healthcheck:
      test: ["CMD-SHELL", "curl -fsSL http://localhost:9200/_cluster/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5

  logstash:
    image: docker.elastic.co/logstash/logstash:7.10.2
    ports:
      - "5000:5000"
    volumes:
      - ./logstash/config/logstash.yml:/usr/share/logstash/config/logstash.yml
      - ./logstash/pipeline:/usr/share/logstash/pipeline
    depends_on:
      - elasticsearch
    networks:
      - hikari
    healthcheck:
      test: ["CMD-SHELL", "curl -fsSL http://localhost:9600/_node/stats || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5

  kibana:
    image: docker.elastic.co/kibana/kibana:7.10.2
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
    networks:
      - hikari
    healthcheck:
      test: ["CMD-SHELL", "curl -fsSL http://localhost:5601/api/status || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5

  fastapi_app:
    build: ../app
    ports:
      - "8000:8000"
    volumes:
      - ../app:/app
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    depends_on:
      kafka:
        condition: service_healthy
      elasticsearch:
        condition: service_healthy
    networks:
      - hikari
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 10s
      retries: 10

networks:
  hikari:
```

#### Script wait_for_health.sh

O script `wait_for_health.sh` verifica continuamente o estado de saúde de todos os serviços configurados no `docker-compose.yml`. Ele aguarda até que todos os serviços estejam marcados como "saudáveis" antes de prosseguir.

```
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
```

### Contato

Se precisar de mais alguma coisa ou tiver alguma dúvida, estou à disposição para ajudar!
