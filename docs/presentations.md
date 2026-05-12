# Presentations Directory Documentation

## Overview

The presentations directory contains presentation materials, demonstration files, and project documentation created by the HIKARI development team. This includes monthly progress presentations, demonstration videos, and simulation scripts used to showcase the platform's capabilities.

## Directory Structure

```
presentations/
├── Caio/                   # Caio's presentations
├── Leonardo/               # Leonardo's presentations and demos
└── Sidnei/                 # Sidnei's presentations and videos
```

## 1. Caio's Presentations (`Caio/`)

### Monthly Progress Presentations

**Files**:
- `HIKARI-04-08.pptx`: April 8th project presentation
- `HIKARI-05-13.pptx`: May 13th project presentation  
- `HIKARI-06-03.pptx`: June 3rd project presentation

**Content Focus**:
- Project evolution and milestone updates
- Technical architecture progress
- Platform development status
- Team coordination and planning

## 2. Leonardo's Presentations (`Leonardo/`)

### Monthly Updates

**Files**:
- `ApresentaçãoAbril.pptx`: April presentation
- `ApresentaçãoMaio.pptx`: May presentation
- `Apresentação_-_Março.pptx`: March presentation

### Demonstration Materials (`mk-1/`)

**Simulation Videos**:
- `simulacao.webm`: Competition simulation demonstration
- `SimulacaoCompeticao.webm`: Competition scenario walkthrough

**Monitoring Scripts**:

**Elasticsearch Monitor** (`monitor-elastic.sh`):
```bash
#!/bin/bash
# Monitor Elasticsearch cluster health and indices
watch -n 2 'curl -s -X GET "localhost:9200/_cluster/health?pretty" && echo "---" && curl -s -X GET "localhost:9200/_cat/indices?v"'
```

**Kafka Monitor** (`monitor-kafka.sh`):
```bash
#!/bin/bash
# Monitor Kafka consumer for competition1 topic
docker exec -it lab_kafka_1 kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic competition1 \
  --from-beginning
```

**Log Injection Script** (`inject-log.sh`):
```bash
#!/bin/bash
# Upload log files to HIKARI API endpoint
curl -X POST "http://localhost:8000/upload_file/" \
  -F "file=@stage1.json"
  
curl -X POST "http://localhost:8000/upload_file/" \
  -F "file=@stage2.json"
```

**Sample Log Files**:

**Stage 1 Data** (`stage1.json`):
```json
[
  {
    "timestamp": "2025-03-25T10:00:00Z",
    "event_type": "network_connection",
    "source_ip": "192.168.1.45",
    "destination_ip": "203.0.113.15",
    "port": 443,
    "protocol": "HTTPS",
    "process": "chrome.exe",
    "flag": "HIKARI{initial_c2_connection}"
  }
]
```

**Stage 2 Data** (`stage2.json`):
```json
[
  {
    "timestamp": "2025-03-25T10:05:00Z",
    "event_type": "file_creation",
    "file_path": "C:\\Users\\victim\\AppData\\Local\\Temp\\malware.exe",
    "process": "powershell.exe",
    "parent_process": "chrome.exe",
    "file_size": 2048576,
    "flag": "HIKARI{malware_dropped}"
  }
]
```

## 3. Sidnei's Presentations (`Sidnei/`)

### Project Documentation

**Files**:
- `HIKARI-Sidnei.pptx`: Sidnei's project presentation
- `Injeção de Logs no Kafka via API.mov`: Video demonstration of Kafka log injection via API

**Content Focus**:
- Kafka integration architecture
- Log injection workflow demonstration
- API endpoints and functionality
- Real-time log processing showcase

## Demonstration Workflow

### Log Injection Process

1. **Preparation**:
   - Start ELK stack and HIKARI platform
   - Verify Kafka and Elasticsearch connectivity
   - Prepare sample log files (stage1.json, stage2.json)

2. **Monitoring Setup**:
   ```bash
   # Terminal 1: Monitor Elasticsearch
   ./monitor-elastic.sh
   
   # Terminal 2: Monitor Kafka
   ./monitor-kafka.sh
   ```

3. **Log Injection**:
   ```bash
   # Inject stage 1 logs
   ./inject-log.sh
   
   # Verify logs in Kibana
   # Access: http://localhost:5601
   ```

4. **Verification**:
   - Check Elasticsearch indices for new documents
   - Verify Kafka topic receives messages
   - Confirm Kibana displays new log entries

### Sample Data Structure

**Common Log Format**:
```json
{
  "timestamp": "ISO 8601 timestamp",
  "event_type": "network_connection|file_creation|process_execution|registry_modification",
  "source_ip": "IP address",
  "destination_ip": "IP address",
  "port": "port number",
  "protocol": "HTTP|HTTPS|TCP|UDP",
  "process": "process name",
  "parent_process": "parent process name",
  "file_path": "file system path",
  "registry_key": "registry key path",
  "flag": "HIKARI{flag_value}",
  "severity": "low|medium|high|critical"
}
```

## Usage in HIKARI Platform

### Competition Scenarios

These presentation materials demonstrate how HIKARI competitions work:

1. **Challenge Creation**: Upload JSON log files with embedded flags
2. **Log Injection**: API automatically streams logs to Kafka
3. **Data Processing**: Logstash processes and indexes logs
4. **Analysis**: Teams use Kibana to analyze logs and find flags
5. **Scoring**: CTFd tracks submissions and team progress

### Training Materials

The presentations serve as:
- **Onboarding**: New team members understand platform capabilities
- **Demonstrations**: Show stakeholders platform functionality
- **Documentation**: Record development progress and decisions
- **Testing**: Verify platform components work correctly

### Technical Validation

The monitoring scripts provide:
- **Real-time Feedback**: Immediate visibility into log processing
- **Debugging**: Troubleshoot issues in the data pipeline
- **Performance Monitoring**: Track system resource usage
- **Integration Testing**: Verify end-to-end functionality

## Development Insights

### Platform Evolution

The monthly presentations reveal:
- **March**: Initial platform concept and architecture
- **April**: Core functionality implementation
- **May**: Advanced features and integrations
- **June**: Platform refinement and optimization

### Key Milestones

1. **CTFd Integration**: Successfully modified CTFd for Blue Team challenges
2. **Kafka Streaming**: Implemented real-time log injection
3. **Elasticsearch Indexing**: Automated log processing and storage
4. **Kibana Visualization**: Team-isolated analysis environments
5. **API Development**: RESTful endpoints for log management

### Technical Challenges

Addressed through development:
- **Scalability**: Multiple team isolation in shared infrastructure
- **Real-time Processing**: Low-latency log streaming
- **Security**: User authentication and data isolation
- **Usability**: Intuitive interface for security analysts

This presentations directory provides valuable documentation of the HIKARI platform's development journey, serving as both technical reference and training material for future users and developers.