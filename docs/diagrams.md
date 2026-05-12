# Diagrams Directory Documentation

## Overview

The diagrams directory contains architectural diagrams and system documentation using PlantUML format. These diagrams provide technical blueprints for deploying and understanding the HIKARI platform's infrastructure, showing how all components interact in both development and production environments.

## Directory Structure

```
diagrams/
├── README.md           # Brief description of diagram contents
├── backend.plantuml    # Backend system architecture
└── hikari.plantuml     # Kubernetes deployment architecture
```

## 1. Backend Architecture (`backend.plantuml`)

### System Overview

The backend diagram illustrates the core HIKARI platform architecture with emphasis on network isolation, log processing, and multi-tenant analysis environments.

### Key Components

**Network Layer**:
```plantuml
@startuml
!theme plain

package "ZeroTier VPN Network" {
  [Network Controller] as zt_controller
  [Network Bridge] as zt_bridge
}

package "Application Layer" {
  [CTFd Platform] as ctfd
  [Python Flask Backend] as flask_backend
  [Admin Interface] as admin_ui
}

package "Message Processing" {
  [Apache Kafka] as kafka
  [Logstash] as logstash
  [Message Queue] as queue
}

package "Data Storage" {
  [Elasticsearch Cluster] as elasticsearch
  [Primary Index] as primary_index
  [Team Indices] as team_indices
}

package "Analysis Layer" {
  [Kibana Instance 1] as kibana1
  [Kibana Instance 2] as kibana2
  [Kibana Instance N] as kibana_n
}

' Network connections
zt_controller --> zt_bridge
zt_bridge --> ctfd
ctfd --> flask_backend
flask_backend --> admin_ui

' Data flow
ctfd --> kafka : Challenge Events
flask_backend --> kafka : Log Injection
kafka --> logstash : Stream Processing
logstash --> elasticsearch : Index Logs
elasticsearch --> primary_index
elasticsearch --> team_indices

' Analysis access
team_indices --> kibana1 : Team 1 Access
team_indices --> kibana2 : Team 2 Access
team_indices --> kibana_n : Team N Access

@enduml
```

### Component Details

**ZeroTier VPN Network**:
- **Purpose**: Secure network isolation for teams
- **Function**: Provides isolated network segments for each team
- **Integration**: Connects to CTFd for automatic network provisioning

**CTFd Platform**:
- **Modified CTFd**: Extended with HIKARI-specific plugins
- **Challenge Management**: Handles Blue Team log analysis challenges
- **Team Coordination**: Manages team registration and progress tracking

**Python Flask Backend**:
- **API Services**: RESTful endpoints for platform management
- **Log Processing**: Handles log file uploads and processing
- **Team Management**: Automates team provisioning and configuration

**Apache Kafka**:
- **Event Streaming**: Real-time log event processing
- **Topic Management**: Separate topics for different data types
- **Scalability**: Handles high-volume log streaming

**Logstash**:
- **Data Transformation**: Processes and enriches log data
- **Multiple Inputs**: Kafka, file uploads, API endpoints
- **Output Routing**: Directs processed logs to appropriate Elasticsearch indices

**Elasticsearch Cluster**:
- **Distributed Storage**: Scalable log storage and indexing
- **Team Isolation**: Separate indices for each team
- **Search Capabilities**: Full-text search and analytics

**Multi-tenant Kibana**:
- **Isolated Instances**: Each team has dedicated Kibana access
- **Custom Dashboards**: Pre-configured analysis dashboards
- **Role-based Access**: Team-specific data access controls

## 2. Kubernetes Deployment (`hikari.plantuml`)

### Production Architecture

The Kubernetes diagram shows the comprehensive deployment architecture for production HIKARI environments, including cloud integration and CI/CD pipelines.

### Infrastructure Components

**Azure Cloud Integration**:
```plantuml
@startuml
!theme plain

package "Azure Cloud Platform" {
  [Azure Container Registry] as acr
  [Azure Load Balancer] as alb
  [Azure SQL Database] as sql_db
  [Azure Storage] as storage
}

package "Kubernetes Cluster" {
  package "System Namespace" {
    [Istio Service Mesh] as istio
    [Ingress Controller] as ingress
    [DNS Service] as dns
  }
  
  package "ELK Namespace" {
    [Elasticsearch Master] as es_master
    [Elasticsearch Data Node 1] as es_data1
    [Elasticsearch Data Node 2] as es_data2
    [Elasticsearch Data Node N] as es_data_n
    [Kibana Service] as kibana_svc
    [Logstash Service] as logstash_svc
    [Kafka Cluster] as kafka_cluster
  }
  
  package "CTFd Namespace" {
    [CTFd-HIKARI Service] as ctfd_hikari
    [Challenge-HIKARI Service] as challenge_hikari
    [Redis Cache] as redis
    [Session Store] as session_store
  }
  
  package "Monitoring Namespace" {
    [Prometheus] as prometheus
    [Grafana] as grafana
    [AlertManager] as alertmanager
  }
}

package "CI/CD Pipeline" {
  [GitHub Repository] as github
  [Azure DevOps] as azure_devops
  [Build Agent] as build_agent
  [Deployment Agent] as deploy_agent
}

' Cloud connections
acr --> ctfd_hikari : Container Images
alb --> ingress : Load Balancing
sql_db --> ctfd_hikari : Database Connection
storage --> elasticsearch : Persistent Storage

' Service mesh
istio --> ingress
ingress --> ctfd_hikari
ingress --> kibana_svc

' ELK stack connections
es_master --> es_data1
es_master --> es_data2
es_master --> es_data_n
kibana_svc --> es_master
logstash_svc --> es_master
kafka_cluster --> logstash_svc

' CTFd connections
ctfd_hikari --> redis
ctfd_hikari --> session_store
ctfd_hikari --> kafka_cluster
challenge_hikari --> ctfd_hikari

' Monitoring
prometheus --> ctfd_hikari : Metrics
prometheus --> es_master : Metrics
grafana --> prometheus : Dashboards
alertmanager --> prometheus : Alerts

' CI/CD flow
github --> azure_devops : Code Changes
azure_devops --> build_agent : Build Trigger
build_agent --> acr : Push Images
deploy_agent --> ctfd_hikari : Deploy

@enduml
```

### Namespace Architecture

**System Namespace**:
- **Istio Service Mesh**: Traffic management and security
- **Ingress Controller**: External traffic routing
- **DNS Service**: Service discovery and name resolution

**ELK Namespace**:
- **Elasticsearch Cluster**: Multi-node setup with master/data separation
- **Kibana Service**: Web interface for log analysis
- **Logstash Service**: Log processing and transformation
- **Kafka Cluster**: Message streaming and event processing

**CTFd Namespace**:
- **CTFd-HIKARI Service**: Modified CTFd application
- **Challenge-HIKARI Service**: Challenge management microservice
- **Redis Cache**: Session and data caching
- **Session Store**: User session management

**Monitoring Namespace**:
- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and dashboards
- **AlertManager**: Alert processing and notifications

### Deployment Specifications

**Elasticsearch Configuration**:
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: elasticsearch-master
  namespace: elk
spec:
  serviceName: elasticsearch-master
  replicas: 3
  template:
    spec:
      containers:
      - name: elasticsearch
        image: docker.elastic.co/elasticsearch/elasticsearch:7.17.10
        env:
        - name: cluster.name
          value: "hikari-cluster"
        - name: node.roles
          value: "master,ingest"
        - name: discovery.seed_hosts
          value: "elasticsearch-master"
        - name: cluster.initial_master_nodes
          value: "es-master-0,es-master-1,es-master-2"
        resources:
          requests:
            memory: 2Gi
            cpu: 1000m
          limits:
            memory: 4Gi
            cpu: 2000m
        volumeMounts:
        - name: data
          mountPath: /usr/share/elasticsearch/data
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 50Gi
      storageClassName: "managed-csi"
```

**CTFd-HIKARI Configuration**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ctfd-hikari
  namespace: ctfd
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ctfd-hikari
  template:
    metadata:
      labels:
        app: ctfd-hikari
    spec:
      containers:
      - name: ctfd-hikari
        image: secdevias/hikari-ctfd:latest
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        - name: REDIS_URL
          value: "redis://redis:6379"
        - name: KAFKA_BOOTSTRAP_SERVERS
          value: "kafka:9092"
        - name: ELASTICSEARCH_URL
          value: "http://elasticsearch-master:9200"
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: 1Gi
            cpu: 500m
          limits:
            memory: 2Gi
            cpu: 1000m
        livenessProbe:
          httpGet:
            path: /healthcheck
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Service Mesh Configuration

**Istio Gateway**:
```yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: hikari-gateway
  namespace: ctfd
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 443
      name: https
      protocol: HTTPS
    tls:
      mode: SIMPLE
      credentialName: hikari-tls-cert
    hosts:
    - "hikari.secdevias.com"
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - "hikari.secdevias.com"
    redirect:
      httpsRedirect: true
```

**Virtual Service**:
```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: hikari-virtualservice
  namespace: ctfd
spec:
  hosts:
  - "hikari.secdevias.com"
  gateways:
  - hikari-gateway
  http:
  - match:
    - uri:
        prefix: "/kibana"
    route:
    - destination:
        host: kibana
        port:
          number: 5601
    headers:
      request:
        add:
          X-Forwarded-Proto: "https"
  - match:
    - uri:
        prefix: "/"
    route:
    - destination:
        host: ctfd-hikari
        port:
          number: 8000
```

## 3. Data Flow Architecture

### Log Processing Pipeline

```plantuml
@startuml
!theme plain

actor "Competition Admin" as admin
actor "Team Members" as team
entity "Challenge Upload" as upload
entity "Log Injection" as injection
entity "Stream Processing" as processing
entity "Data Storage" as storage
entity "Analysis Interface" as analysis

admin -> upload : Upload Challenge Logs
upload -> injection : Trigger Log Injection
injection -> processing : Stream to Kafka
processing -> storage : Index in Elasticsearch
storage -> analysis : Query via Kibana
analysis -> team : Team Analysis

note right of injection : Triggered by challenge completion
note right of processing : Real-time log enrichment
note right of storage : Team-isolated indices
note right of analysis : Role-based access control

@enduml
```

### Security Architecture

```plantuml
@startuml
!theme plain

package "Security Layer" {
  [Istio Security] as istio_security
  [Network Policies] as network_policies
  [RBAC] as rbac
  [TLS Termination] as tls
}

package "Authentication" {
  [OAuth2 Provider] as oauth2
  [JWT Tokens] as jwt
  [Session Management] as session
}

package "Authorization" {
  [Team Isolation] as team_isolation
  [Index Permissions] as index_permissions
  [API Rate Limiting] as rate_limiting
}

istio_security --> network_policies
network_policies --> rbac
rbac --> tls

oauth2 --> jwt
jwt --> session
session --> team_isolation

team_isolation --> index_permissions
index_permissions --> rate_limiting

@enduml
```

## Usage Instructions

### Generating Diagrams

1. **Install PlantUML**:
   ```bash
   # Using Java
   wget http://sourceforge.net/projects/plantuml/files/plantuml.jar/download
   
   # Using package manager
   sudo apt-get install plantuml
   ```

2. **Generate SVG/PNG**:
   ```bash
   # Backend architecture
   plantuml -tsvg backend.plantuml
   
   # Kubernetes deployment
   plantuml -tpng hikari.plantuml
   ```

3. **View in Browser**:
   ```bash
   # Open generated files
   firefox backend.svg
   firefox hikari.png
   ```

### Customization

**Modify Components**:
- Edit `.plantuml` files to update architecture
- Add new components or connections
- Adjust styling and layouts

**Export Formats**:
- SVG: Vector graphics for documentation
- PNG: Raster images for presentations
- PDF: Print-ready documentation

## Architecture Benefits

### Scalability
- **Horizontal Scaling**: Add more Elasticsearch nodes
- **Load Distribution**: Istio load balancing
- **Auto-scaling**: Kubernetes HPA support

### Security
- **Network Isolation**: Istio service mesh
- **Data Segregation**: Team-specific indices
- **Authentication**: OAuth2 integration
- **Authorization**: Role-based access control

### Reliability
- **High Availability**: Multi-replica deployments
- **Fault Tolerance**: Elasticsearch cluster redundancy
- **Monitoring**: Prometheus/Grafana integration
- **Disaster Recovery**: Automated backups

### Maintainability
- **Microservices**: Loosely coupled components
- **CI/CD Integration**: Automated deployments
- **Configuration Management**: Kubernetes manifests
- **Documentation**: PlantUML diagrams

These diagrams provide comprehensive technical documentation for the HIKARI platform architecture, enabling effective deployment, maintenance, and scaling of the Blue Team training environment.