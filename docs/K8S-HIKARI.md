# K8S-HIKARI Documentation

## Overview

K8S-HIKARI provides a complete Kubernetes deployment infrastructure for the HIKARI Blue Team competition platform. It includes infrastructure provisioning, ELK stack deployment, CTFd application deployment, and comprehensive backup solutions.

## Directory Structure

```
K8S-HIKARI/
├── backup-velero/           # Velero backup configuration
├── ctfd-image/              # CTFd Kubernetes deployment
├── elk-zerotier-install/    # ELK stack with Kafka deployment
└── infra-from-virtualbox/   # Infrastructure provisioning
```

## 1. Infrastructure Provisioning (`infra-from-virtualbox/`)

### Hardware Optimization System

**Cluster Specifications** (`cluster_specs.py`):
- Dynamically calculates optimal VM distribution based on physical resources
- Ensures even CPU core allocation per VM
- Reserves resources for host OS (4GB RAM, 2 CPUs)
- Generates cluster configuration YAML

**VM Management** (`Vagrantfile`):
- VirtualBox VM provisioning with Ubuntu 24.10
- Automated SSH key distribution
- Network configuration for cluster communication

### Kubernetes Bootstrapping

**Main Orchestration Script** (`bootstrap_k8s_cluster.py`):
1. Runs cluster specification calculations
2. Provisions VMs via Vagrant
3. Generates Ansible inventory for nodes
4. Installs Kubespray
5. Retrieves Kubernetes credentials
6. Installs kubectl
7. Executes post-installation scripts

**Key Scripts**:
- `generate_inventory.py`: Creates Ansible inventory for cluster nodes
- `install_kubespray.sh`: Deploys Kubernetes using Kubespray
- `get_k8s_creds.sh`: Extracts and configures kubectl credentials

### Storage Configuration

**Rook Ceph Setup**:
- `generate_rook_yaml.py`: Rook Ceph storage cluster setup
- `rookfs_postinstall.sh`: Post-installation storage configuration
- `storageclass.yaml`: Dynamic storage provisioning

## 2. ELK Stack Deployment (`elk-zerotier-install/`)

### Components

**Elasticsearch Cluster**:
- 3-replica cluster with anti-affinity rules
- 4Gi-8Gi memory allocation per pod
- 50Gi persistent storage using Rook Ceph
- Security enabled with TLS and authentication

**Kafka Event Streaming**:
- Bitnami Kafka chart deployment
- SASL authentication with user management
- Topic: `competition1` for CTF event logging

**Logstash Processing**:
- Dual input sources: Beats (port 5044) and Kafka
- SASL/SCRAM-SHA-256 authentication for Kafka
- Elasticsearch output with TLS verification

**Kibana Dashboard**:
- Web interface for log analysis
- Automated index pattern creation
- Role-based access control

### Deployment Scripts

**Main Deployment** (`kube_deploy.sh`):
```bash
#!/bin/bash
# Deploys ELK stack with Kafka integration
# Includes pod readiness verification
# Credential extraction and management
# Error handling and rollback capabilities
```

**Post-Deployment Configuration** (`kube_configure.sh`):
```bash
#!/bin/bash
# Elasticsearch user/role setup
# Kibana index pattern creation
# Kafka topic verification
# End-to-end testing with message verification
```

### Configuration Files

**Elasticsearch Values** (`elastic-values.yaml`):
```yaml
replicas: 3
minimumMasterNodes: 2
persistence:
  size: 50Gi
  storageClass: "rook-ceph-block"
resources:
  requests:
    memory: 4Gi
  limits:
    memory: 8Gi
```

**Kafka Values** (`kafka-values.yaml`):
```yaml
auth:
  clientProtocol: sasl
  sasl:
    mechanisms: scram-sha-256
    users:
      - user1
persistence:
  enabled: true
  size: 20Gi
  storageClass: "rook-ceph-block"
```

**Logstash Values** (`logstash-values.yaml`):
```yaml
logstashConfig:
  logstash.yml: |
    http.host: "0.0.0.0"
    xpack.monitoring.enabled: true
    xpack.monitoring.elasticsearch.hosts: ["https://elasticsearch:9200"]

logstashPipeline:
  logstash.conf: |
    input {
      kafka {
        bootstrap_servers => "kafka:9092"
        topics => ["competition1"]
        security_protocol => "SASL_PLAINTEXT"
        sasl_mechanism => "SCRAM-SHA-256"
        sasl_jaas_config => "org.apache.kafka.common.security.scram.ScramLoginModule required username='user1' password='password';"
      }
    }
    
    output {
      elasticsearch {
        hosts => ["https://elasticsearch:9200"]
        index => "logs-%{+YYYY.MM.dd}"
        ssl => true
        ssl_certificate_verification => false
      }
    }
```

## 3. CTFd Application Deployment (`ctfd-image/`)

### Components

**CTFd Application** (`ctfd-deployment.yaml`):
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ctfd
  namespace: ctfd
spec:
  replicas: 1
  strategy:
    type: RollingUpdate
  template:
    spec:
      containers:
      - name: ctfd
        image: secdevias/hikari-ctfd:0.0.2
        env:
        - name: DATABASE_URL
          value: "mysql://ctfd:password@mariadb:3306/ctfd"
        - name: REDIS_URL
          value: "redis://redis:6379"
        - name: KAFKA_BOOTSTRAP_SERVERS
          value: "kafka:9092"
```

**Database Layer** (`ctfd-mariadb.yaml`):
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mariadb
  namespace: ctfd
spec:
  serviceName: mariadb
  replicas: 1
  template:
    spec:
      containers:
      - name: mariadb
        image: mariadb:10.11
        env:
        - name: MYSQL_ROOT_PASSWORD
          value: "rootpassword"
        - name: MYSQL_DATABASE
          value: "ctfd"
        - name: MYSQL_USER
          value: "ctfd"
        - name: MYSQL_PASSWORD
          value: "password"
  volumeClaimTemplates:
  - metadata:
      name: mariadb-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 8Gi
      storageClassName: "rook-ceph-block"
```

**Caching Layer** (`ctfd-redis.yaml`):
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: ctfd
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: redis
        image: redis:7
        command: ["redis-server", "--appendonly", "yes"]
        volumeMounts:
        - name: redis-data
          mountPath: /data
  volumeClaimTemplates:
  - metadata:
      name: redis-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 2Gi
      storageClassName: "rook-ceph-block"
```

### Networking Configuration

**Istio Gateway** (`ctfd-gateway.yaml`):
```yaml
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: ctfd-gateway
  namespace: ctfd
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - "*"
```

**Virtual Service** (`ctfd-virtualservice.yaml`):
```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: ctfd-virtualservice
  namespace: ctfd
spec:
  hosts:
  - "*"
  gateways:
  - ctfd-gateway
  http:
  - match:
    - uri:
        prefix: "/"
    route:
    - destination:
        host: ctfd
        port:
          number: 8000
```

### Deployment Script (`deploy.sh`)

```bash
#!/bin/bash
# Automated deployment script

# Fetch Kafka credentials from elk namespace
KAFKA_PASSWORD=$(kubectl get secret kafka-user-passwords -n elk -o jsonpath='{.data.client-passwords}' | base64 -d | cut -d, -f1)

# Substitute environment variables in configuration templates
export KAFKA_PASSWORD
envsubst < ctfd-configmap-template.yaml > ctfd-configmap.yaml

# Deploy all Kubernetes resources
kubectl apply -f ctfd-namespace.yaml
kubectl apply -f ctfd-configmap.yaml
kubectl apply -f ctfd-mariadb.yaml
kubectl apply -f ctfd-redis.yaml
kubectl apply -f ctfd-deployment.yaml
kubectl apply -f ctfd-gateway.yaml
kubectl apply -f ctfd-virtualservice.yaml

# Verify deployment
kubectl get pods -n ctfd
```

## 4. Backup Configuration (`backup-velero/`)

### Velero Backup System

**AWS S3 Backend Configuration**:
- Bucket: `tkg-velero-backups` in sa-east-1 region
- File system backup for persistent volumes
- Namespace-based granular backup
- Retention policy: 8760h (1 year) TTL

**Volume Discovery Script** (`probevolumes.sh`):
```bash
#!/bin/bash
# Identifies PVCs and mount points for backup annotation
# Automated volume discovery and annotation for Velero
# Support for StatefulSet and Deployment persistent volumes

kubectl get pvc -A -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,VOLUME:.spec.volumeName --no-headers | while read namespace name volume; do
    echo "Namespace: $namespace, PVC: $name, Volume: $volume"
    kubectl annotate pvc $name -n $namespace backup.velero.io/backup-volumes=$volume
done
```

### Backup Workflow

1. **Install Velero CLI**:
```bash
curl -fsSL -o velero-v1.12.1-linux-amd64.tar.gz https://github.com/vmware-tanzu/velero/releases/download/v1.12.1/velero-v1.12.1-linux-amd64.tar.gz
tar -xzf velero-v1.12.1-linux-amd64.tar.gz
sudo mv velero-v1.12.1-linux-amd64/velero /usr/local/bin/
```

2. **Create AWS Credentials**:
```bash
cat > credentials-velero <<EOF
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
EOF
```

3. **Deploy Velero**:
```bash
velero install \
    --provider aws \
    --plugins velero/velero-plugin-for-aws:v1.8.1 \
    --bucket tkg-velero-backups \
    --backup-location-config region=sa-east-1 \
    --snapshot-location-config region=sa-east-1 \
    --secret-file ./credentials-velero \
    --use-node-agent
```

4. **Create Namespace Backup**:
```bash
velero backup create hikari-backup \
    --include-namespaces ctfd,elk \
    --default-volumes-to-fs-backup \
    --ttl 8760h \
    --wait
```

5. **Restore from Backup**:
```bash
velero restore create --from-backup hikari-backup
```

## Deployment Architecture

### Overall Flow

```
1. Infrastructure Layer
   └── VirtualBox VMs (Ubuntu 24.10)
   └── Kubernetes cluster via Kubespray
   └── Rook Ceph storage cluster

2. Platform Layer
   └── Elasticsearch cluster (3 nodes)
   └── Kafka for event streaming
   └── Logstash for log processing
   └── Kibana for visualization

3. Application Layer
   └── CTFd application deployment
   └── MariaDB database
   └── Redis caching
   └── Istio service mesh integration

4. Backup Layer
   └── Velero with AWS S3 backend
   └── Persistent volume backup
   └── Namespace-level disaster recovery
```

### Key Integration Points

- **Kafka Integration**: CTFd publishes events to Kafka topic `competition1`
- **Log Processing**: Logstash consumes Kafka events and indexes to Elasticsearch
- **Monitoring**: Kibana provides real-time CTF event visualization
- **Service Mesh**: Istio handles traffic management and security
- **Storage**: Rook Ceph provides distributed storage for all persistent volumes

## Security Features

- TLS encryption for all inter-service communication
- SASL/SCRAM authentication for Kafka
- Role-based access control in Elasticsearch
- Network policies via Istio service mesh
- Encrypted persistent volume storage

## Usage

### Full Deployment

1. **Provision Infrastructure**:
```bash
cd infra-from-virtualbox/
python3 bootstrap_k8s_cluster.py
```

2. **Deploy ELK Stack**:
```bash
cd elk-zerotier-install/
./kube_deploy.sh
./kube_configure.sh
```

3. **Deploy CTFd**:
```bash
cd ctfd-image/
./deploy.sh
```

4. **Setup Backup**:
```bash
cd backup-velero/
# Configure AWS credentials
# Deploy Velero
# Run probevolumes.sh to annotate PVCs
```

### Monitoring and Maintenance

- **Check Pod Status**: `kubectl get pods -A`
- **View Logs**: `kubectl logs -f deployment/ctfd -n ctfd`
- **Scale Components**: `kubectl scale deployment ctfd --replicas=3 -n ctfd`
- **Backup Status**: `velero backup get`

This infrastructure provides a robust, scalable, and highly available platform for hosting CTF competitions with comprehensive logging, monitoring, and backup capabilities.