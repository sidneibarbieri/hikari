#!/bin/bash
set -euo pipefail

# === Configuration ===
NAMESPACE="elk"
KAFKA_RELEASE_NAME="kafka"
ELASTICSEARCH_RELEASE_NAME="elasticsearch"
LOGSTASH_RELEASE_NAME="logstash"
KIBANA_RELEASE_NAME="kibana"

KAFKA_CHART="bitnami/kafka"
ELASTICSEARCH_CHART="elastic/elasticsearch"
LOGSTASH_CHART="elastic/logstash"
KIBANA_CHART="elastic/kibana"

KAFKA_VALUES="./kafka-values.yaml"
ELASTICSEARCH_VALUES="./elastic-values.yaml"
LOGSTASH_VALUES="./logstash-values.yaml"
KIBANA_VALUES="./kibana-values.yaml"

CREDS_DIR="./kube_creds"
ES_CACERT_FILE="${CREDS_DIR}/elastic-ca.crt"
ES_PASSWORD_FILE="${CREDS_DIR}/es_password.txt"
KAFKA_PASSWORD_FILE="${CREDS_DIR}/kafka_user1_password.txt"

HELM_TIMEOUT="10m"
KUBECTL_TIMEOUT="8m"

log_info() { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $1"; }
log_warn() { echo "[WARN] $(date '+%Y-%m-%d %H:%M:%S') - $1"; }
log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $1" >&2; }
command_exists() { command -v "$1" >/dev/null 2>&1; }

# Wait for Bitnami Kafka StatefulSet pods to be Ready
wait_for_kafka_pods() {
  local release_name="$1" ns="$2" timeout="$3"
  local sts_name="${release_name}-controller"
  local selector="app.kubernetes.io/component=controller-eligible,app.kubernetes.io/instance=${release_name},app.kubernetes.io/name=kafka,app.kubernetes.io/part-of=kafka"

  log_info "Waiting for Kafka pods in '$sts_name' to be Ready..."
  if ! kubectl get statefulset "$sts_name" -n "$ns" >/dev/null 2>&1; then
    sleep 15
    if ! kubectl get statefulset "$sts_name" -n "$ns" >/dev/null 2>&1; then
      log_error "StatefulSet '$sts_name' not found."
      exit 1
    fi
  fi

  if ! kubectl wait --for=condition=Ready pods -l "$selector" -n "$ns" --timeout="$timeout"; then
    log_error "Kafka pods did not become ready."
    exit 1
  fi
  log_info "Kafka pods are ready."
}

# Wait for Elasticsearch StatefulSet pods to be Ready
wait_for_elastic_pods() {
  local sts_name="$1" ns="$2" timeout="$3"
  local selector="app=${sts_name}"

  log_info "Waiting for Elasticsearch pods in '$sts_name'..."
  if ! kubectl get statefulset "$sts_name" -n "$ns" >/dev/null 2>&1; then
    sleep 15
    if ! kubectl get statefulset "$sts_name" -n "$ns" >/dev/null 2>&1; then
      log_error "StatefulSet '$sts_name' not found."
      exit 1
    fi
  fi

  if ! kubectl wait --for=condition=Ready pods -l "$selector" -n "$ns" --timeout="$timeout"; then
    log_error "Elasticsearch pods not ready."
    exit 1
  fi
  log_info "Elasticsearch pods are ready."
}

# Wait for Deployment to be Available (Kibana, Logstash)
wait_for_deployment() {
  local release_name="$1" ns="$2" timeout="$3"
  local expected_name="${release_name}-${release_name}"
  local selector="app=${expected_name}"

  sleep 5
  if ! kubectl get deployment "$expected_name" -n "$ns" >/dev/null 2>&1; then
    log_error "Deployment '$expected_name' not found."
    exit 1
  fi

  if ! kubectl wait --for=condition=Available=True deployment/"$expected_name" -n "$ns" --timeout="$timeout"; then
    log_error "Deployment '$expected_name' not ready."
    exit 1
  fi
  log_info "Deployment '$expected_name' is available."
}

# Wait for Logstash StatefulSet
wait_for_logstash_pods() {
  local sts_name="$1" ns="$2" timeout="$3"
  local selector="app=${sts_name}"
  sleep 5

  if ! kubectl get statefulset "$sts_name" -n "$ns" >/dev/null 2>&1; then
    log_error "StatefulSet '$sts_name' not found."
    exit 1
  fi

  if ! kubectl wait --for=condition=Ready pods -l "$selector" -n "$ns" --timeout="$timeout"; then
    log_error "Logstash pods not ready."
    exit 1
  fi
  log_info "Logstash pods are ready."
}

# Install or upgrade Helm release
install_or_upgrade_chart() {
  local release_name="$1" chart_name="$2" ns="$3" values_file="$4"

  log_info "Installing/upgrading '$release_name'..."
  if ! helm upgrade --install "$release_name" "$chart_name" \
    --namespace "$ns" \
    --create-namespace \
    -f "$values_file" \
    --wait \
    --timeout "$HELM_TIMEOUT"; then
    log_error "Helm failed for '$release_name'"
    exit 1
  fi
  log_info "Helm install succeeded for '$release_name'."
}

# === Pre-flight ===
log_info "Checking required commands..."
for cmd in kubectl helm jq base64 curl; do
  if ! command_exists "$cmd"; then
    log_error "Missing required command: $cmd"
    exit 1
  fi
done

for val_file in "$KAFKA_VALUES" "$ELASTICSEARCH_VALUES" "$LOGSTASH_VALUES" "$KIBANA_VALUES"; do
  if [ ! -f "$val_file" ]; then
    log_error "Missing values file: $val_file"
    exit 1
  fi
done
log_info "All values files and tools are present."

# === Deployment Start ===
log_info "Starting deployment..."
mkdir -p "$CREDS_DIR"

install_or_upgrade_chart "$KAFKA_RELEASE_NAME" "$KAFKA_CHART" "$NAMESPACE" "$KAFKA_VALUES"
wait_for_kafka_pods "$KAFKA_RELEASE_NAME" "$NAMESPACE" "$KUBECTL_TIMEOUT"

install_or_upgrade_chart "$ELASTICSEARCH_RELEASE_NAME" "$ELASTICSEARCH_CHART" "$NAMESPACE" "$ELASTICSEARCH_VALUES"
wait_for_elastic_pods "${ELASTICSEARCH_RELEASE_NAME}-master" "$NAMESPACE" "$KUBECTL_TIMEOUT"

install_or_upgrade_chart "$LOGSTASH_RELEASE_NAME" "$LOGSTASH_CHART" "$NAMESPACE" "$LOGSTASH_VALUES"
wait_for_logstash_pods "${LOGSTASH_RELEASE_NAME}-${LOGSTASH_RELEASE_NAME}" "$NAMESPACE" "$KUBECTL_TIMEOUT"

install_or_upgrade_chart "$KIBANA_RELEASE_NAME" "$KIBANA_CHART" "$NAMESPACE" "$KIBANA_VALUES"
wait_for_deployment "$KIBANA_RELEASE_NAME" "$NAMESPACE" "$KUBECTL_TIMEOUT"

# === Retrieve credentials ===
log_info "Fetching credentials..."

retries=3 delay=5
while [[ $retries -gt 0 ]]; do
  ES_PASSWORD=$(kubectl get secret "${ELASTICSEARCH_RELEASE_NAME}-master-credentials" -n "$NAMESPACE" -o jsonpath="{.data.password}" 2>/dev/null | base64 --decode)
  [ -n "$ES_PASSWORD" ] && break
  sleep $delay; retries=$((retries - 1))
done
[ -z "$ES_PASSWORD" ] && log_error "Failed to get ES password" && exit 1
echo "$ES_PASSWORD" > "$ES_PASSWORD_FILE"

retries=3
while [[ $retries -gt 0 ]]; do
  ES_CACERT_DATA=$(kubectl get secret "${ELASTICSEARCH_RELEASE_NAME}-master-certs" -n "$NAMESPACE" -o jsonpath="{.data.ca\.crt}" 2>/dev/null)
  [ -n "$ES_CACERT_DATA" ] && break
  sleep $delay; retries=$((retries - 1))
done
[ -z "$ES_CACERT_DATA" ] && log_error "Failed to get ES CA cert" && exit 1
echo "$ES_CACERT_DATA" | base64 --decode > "$ES_CACERT_FILE"

retries=3
while [[ $retries -gt 0 ]]; do
  KAFKA_PASSWORD_RAW=$(kubectl get secret "${KAFKA_RELEASE_NAME}-user-passwords" -n "$NAMESPACE" -o jsonpath='{.data.client-passwords}' 2>/dev/null)
  [ -n "$KAFKA_PASSWORD_RAW" ] && break
  sleep $delay; retries=$((retries - 1))
done

if [ -z "$KAFKA_PASSWORD_RAW" ]; then
  echo "PASSWORD_NOT_FOUND" > "$KAFKA_PASSWORD_FILE"
else
  KAFKA_PASSWORD=$(echo "$KAFKA_PASSWORD_RAW" | base64 -d | cut -d , -f 1)
  echo "$KAFKA_PASSWORD" > "$KAFKA_PASSWORD_FILE"
fi

# === Done ===
log_info "Final pod status:"
kubectl get pods -n "$NAMESPACE" -o wide

log_info "--------------------------------------------------"
log_info "Deployment complete. Run './kube_configure.sh' next."
log_info "--------------------------------------------------"

exit 0

