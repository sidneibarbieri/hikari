# Lab Directory Documentation

## Overview

The lab directory contains a comprehensive development and testing environment for the HIKARI platform, featuring an ELK stack, FastAPI application, and threat intelligence data processing capabilities. This environment serves as both a development testbed and a threat hunting platform with real APT29 data.

## Directory Structure

```
lab/
├── app/                    # FastAPI application
├── apt29/                  # Threat intelligence data
├── docker/                 # ELK stack deployment
├── docker-old/             # Legacy configuration
├── scripts/                # Analysis notebooks
└── venv/                   # Python virtual environment
```

## 1. FastAPI Application (`app/`)

### Core Application (`main.py`)

A FastAPI application serving as a Kafka producer API with comprehensive log processing capabilities.

**Endpoints**:
- `GET /`: Welcome message and health check
- `GET /run_scenario/`: Starts threat simulation scenarios
- `POST /upload_file/`: Processes and streams JSON log files to Kafka

**Key Features**:
```python
# Kafka integration with health checks
@app.get("/run_scenario/")
async def run_scenario():
    producer = KafkaProducer(bootstrap_servers='kafka:9092')
    # Process and send simulation data
    
@app.post("/upload_file/")
async def upload_file(file: UploadFile):
    # JSON validation and processing
    # Stream to Kafka topic
```

### Configuration Files

**Dockerfile**:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc libpq-dev curl
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Dependencies** (`requirements.txt`):
- FastAPI and Uvicorn for web framework
- Kafka-python for message streaming
- Elasticsearch client for direct queries
- Pytest and testing utilities

**Logging Configuration** (`logging_config.yaml`):
```yaml
version: 1
disable_existing_loggers: false
formatters:
  default:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
handlers:
  console:
    class: logging.StreamHandler
    formatter: default
    stream: ext://sys.stdout
loggers:
  uvicorn:
    level: INFO
    handlers: [console]
    propagate: false
```

### Testing Framework

**Test Suite** (`test_app.py`):
```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome to HIKARI" in response.json()["message"]

@patch('main.KafkaProducer')
def test_upload_file_json(mock_producer):
    # Test JSON file upload with mocked Kafka
    mock_producer_instance = MagicMock()
    mock_producer.return_value = mock_producer_instance
    
    response = client.post("/upload_file/", files={"file": ("test.json", json_content, "application/json")})
    assert response.status_code == 200
```

## 2. ELK Stack Deployment (`docker/`)

### Docker Compose Configuration

**Architecture**:
```yaml
version: '3.8'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.4.0
    ports: ["2181:2181"]
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    healthcheck:
      test: ["CMD", "echo", "ruok", "|", "nc", "localhost", "2181"]
      interval: 30s
      timeout: 10s
      retries: 3

  kafka:
    image: confluentinc/cp-kafka:7.4.0
    ports: ["9092:9092"]
    depends_on:
      zookeeper:
        condition: service_healthy
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    healthcheck:
      test: ["CMD", "kafka-topics", "--bootstrap-server", "localhost:9092", "--list"]
      interval: 30s
      timeout: 10s
      retries: 3

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.17.10
    ports: ["9200:9200", "9300:9300"]
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=true
      - ELASTIC_PASSWORD=adminPass123
      - ES_JAVA_OPTS=-Xms1g -Xmx1g
    healthcheck:
      test: ["CMD-SHELL", "curl -s -u elastic:adminPass123 http://localhost:9200/_cluster/health | grep -q '\"status\":\"green\"'"]
      interval: 30s
      timeout: 10s
      retries: 5

  logstash:
    image: docker.elastic.co/logstash/logstash:7.17.10
    ports: ["5000:5000", "9600:9600"]
    depends_on:
      elasticsearch:
        condition: service_healthy
      kafka:
        condition: service_healthy
    volumes:
      - ./logstash/config/logstash.yml:/usr/share/logstash/config/logstash.yml
      - ./logstash/pipeline:/usr/share/logstash/pipeline
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9600"]
      interval: 30s
      timeout: 10s
      retries: 5

  kibana:
    image: docker.elastic.co/kibana/kibana:7.17.10
    ports: ["5601:5601"]
    depends_on:
      elasticsearch:
        condition: service_healthy
    environment:
      - ELASTICSEARCH_URL=http://elasticsearch:9200
      - ELASTICSEARCH_USERNAME=elastic
      - ELASTICSEARCH_PASSWORD=adminPass123
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5601/api/status"]
      interval: 30s
      timeout: 10s
      retries: 5

  fastapi_app:
    build: ../app
    ports: ["8000:8000"]
    depends_on:
      kafka:
        condition: service_healthy
      elasticsearch:
        condition: service_healthy
    environment:
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
      - ELASTICSEARCH_URL=http://elasticsearch:9200
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 10s
      retries: 5
```

### Logstash Configuration

**Pipeline Configuration** (`logstash/pipeline/logstash.conf`):
```ruby
input {
  kafka {
    bootstrap_servers => "kafka:9092"
    topics => ["competition1", "threat-intelligence"]
    codec => "json"
    consumer_threads => 1
    decorate_events => true
  }
  
  http {
    port => 5000
    codec => json
  }
}

filter {
  # Add timestamp if not present
  if ![timestamp] {
    mutate {
      add_field => { "timestamp" => "%{[@timestamp]}" }
    }
  }
  
  # Grok patterns for common log formats
  grok {
    match => { "message" => "%{COMBINEDAPACHELOG}" }
    tag_on_failure => ["_grokparsefailure"]
  }
  
  # IP geolocation
  geoip {
    source => "clientip"
    target => "geoip"
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "logs-%{+YYYY.MM.dd}"
    user => "elastic"
    password => "adminPass123"
    ssl => false
    ssl_certificate_verification => false
  }
  
  stdout {
    codec => rubydebug
  }
}
```

### Setup Scripts

**Master Setup Script** (`scripts/run-all.sh`):
```bash
#!/bin/bash
set -e

echo "Starting HIKARI Lab Environment Setup..."

# Wait for Elasticsearch to be ready
echo "Waiting for Elasticsearch..."
until curl -s -u elastic:adminPass123 http://elasticsearch:9200/_cluster/health | grep -q "green"; do
    sleep 10
done

# Setup Elasticsearch users and roles
echo "Setting up Elasticsearch users..."
./setup_elasticsearch.sh

# Setup Kibana index patterns
echo "Setting up Kibana..."
./setup_kibana.sh

# Verify pipeline
echo "Verifying pipeline..."
./check_pipeline.sh

echo "Setup complete!"
```

**Elasticsearch Setup** (`scripts/setup_elasticsearch.sh`):
```bash
#!/bin/bash
# Create read-only user for dashboard access
curl -X POST "elasticsearch:9200/_security/user/dashboard_user" \
  -H "Content-Type: application/json" \
  -u elastic:adminPass123 \
  -d '{
    "password": "dashboardPass123",
    "roles": ["kibana_dashboard_only_user", "viewer"],
    "full_name": "Dashboard User",
    "email": "dashboard@hikari.local"
  }'

# Create viewer role
curl -X POST "elasticsearch:9200/_security/role/viewer" \
  -H "Content-Type: application/json" \
  -u elastic:adminPass123 \
  -d '{
    "indices": [
      {
        "names": ["logs-*"],
        "privileges": ["read", "view_index_metadata"]
      }
    ]
  }'
```

**Kibana Setup** (`scripts/setup_kibana.sh`):
```bash
#!/bin/bash
# Create index pattern
curl -X POST "kibana:5601/api/saved_objects/index-pattern/logs-*" \
  -H "Content-Type: application/json" \
  -H "kbn-xsrf: true" \
  -u elastic:adminPass123 \
  -d '{
    "attributes": {
      "title": "logs-*",
      "timeFieldName": "@timestamp"
    }
  }'

# Publish test message
curl -X POST "fastapi_app:8000/upload_file/" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/app/test.json"
```

## 3. Threat Intelligence Data (`apt29/`)

### APT29 Evaluation Data

**Dataset Overview**:
- **Day 1**: 196,081 log entries (apt29_evals_day1_manual_2020-05-01225525.json)
- **Day 2**: 587,286 log entries (apt29_evals_day2_manual_2020-05-02035409.json)
- **Total**: 783,367 entries from real APT29 security evaluation exercises

**Data Characteristics**:
```json
{
  "timestamp": "2020-05-01T22:55:25.000Z",
  "host": "victim-workstation",
  "event_type": "process_creation",
  "process_name": "powershell.exe",
  "command_line": "powershell.exe -nop -w hidden -c ...",
  "parent_process": "explorer.exe",
  "source_ip": "10.0.1.45",
  "destination_ip": "192.168.1.100",
  "port": 443,
  "protocol": "HTTPS"
}
```

**Network Infrastructure**:
- Internal IP ranges: 10.0.x.x, 192.168.x.x, 172.18.x.x
- External C2 infrastructure
- DNS queries and responses
- HTTP/HTTPS traffic logs

## 4. Analysis Scripts (`scripts/`)

### Data Processing Notebook (`script01.ipynb`)

**Key Functions**:
```python
import json
import pandas as pd
from datetime import datetime, timedelta
from tqdm import tqdm

def process_apt29_data(file_path):
    """Process APT29 data and adjust timestamps to current time"""
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    # Calculate time offset
    base_time = datetime.strptime(data[0]['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
    current_time = datetime.now()
    time_offset = current_time - base_time
    
    # Process entries with progress bar
    processed_data = []
    for entry in tqdm(data, desc="Processing entries"):
        # Adjust timestamp
        original_time = datetime.strptime(entry['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
        new_time = original_time + time_offset
        entry['timestamp'] = new_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        processed_data.append(entry)
    
    return processed_data

def combine_datasets(day1_data, day2_data):
    """Combine and sort datasets chronologically"""
    combined = day1_data + day2_data
    combined.sort(key=lambda x: x['timestamp'])
    return combined
```

### Network Analysis Notebook (`script02.ipynb`)

**Network Topology Analysis**:
```python
import ipaddress
import re

def extract_internal_ips(data):
    """Extract internal IP addresses from log data"""
    internal_ips = set()
    
    for entry in data:
        # Extract IPs from various fields
        for field in ['source_ip', 'destination_ip', 'host_ip']:
            if field in entry:
                ip = entry[field]
                if is_internal_ip(ip):
                    internal_ips.add(ip)
    
    return list(internal_ips)

def is_internal_ip(ip_str):
    """Check if IP is in private ranges"""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private
    except ValueError:
        return False

def analyze_network_segments(internal_ips):
    """Analyze network segments and subnets"""
    segments = {}
    for ip in internal_ips:
        network = ipaddress.ip_network(f"{ip}/24", strict=False)
        if network not in segments:
            segments[network] = []
        segments[network].append(ip)
    
    return segments
```

## 5. Legacy Configuration (`docker-old/`)

### Simplified Docker Compose

**Key Differences**:
- No Elasticsearch security/authentication
- Basic Logstash configuration
- No orchestrator container
- Simplified health checks

**Basic Configuration**:
```yaml
version: '3.7'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.10.2
    environment:
      - discovery.type=single-node
      # No security configuration
    
  logstash:
    image: docker.elastic.co/logstash/logstash:7.10.2
    volumes:
      - ./logstash/pipeline:/usr/share/logstash/pipeline
    # Basic configuration without authentication
```

## Usage

### Starting the Lab Environment

1. **Launch ELK Stack**:
```bash
cd lab/docker
docker-compose up -d
```

2. **Verify Health**:
```bash
./scripts/check_pipeline.sh
```

3. **Access Services**:
- FastAPI: http://localhost:8000
- Kibana: http://localhost:5601 (elastic/adminPass123)
- Elasticsearch: http://localhost:9200

### Testing Data Upload

```bash
# Upload test data
curl -X POST "http://localhost:8000/upload_file/" \
  -F "file=@app/example.json"

# Run threat simulation
curl -X GET "http://localhost:8000/run_scenario/"
```

### Processing APT29 Data

```bash
cd lab/scripts
jupyter notebook script01.ipynb
# Process and combine APT29 datasets
```

## Security Features

- **Authentication**: Elasticsearch with admin (elastic/adminPass123) and read-only users
- **Role-based Access**: Kibana dashboard-only roles for limited access
- **Network Isolation**: Custom Docker network for service communication
- **Health Monitoring**: Comprehensive health checks for all services

## Use Cases

- **Threat Intelligence Processing**: APT29 data analysis and simulation
- **Security Analytics**: Log analysis and correlation
- **Competition Development**: CTF-style security challenges
- **Research Platform**: Security tool testing and validation

This lab environment provides a realistic threat hunting platform with actual APT29 data, making it valuable for security research, training, and competition scenarios.