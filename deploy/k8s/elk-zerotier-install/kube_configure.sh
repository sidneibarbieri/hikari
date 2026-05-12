#!/bin/bash
set -euo pipefail

# === Configuration ===
NAMESPACE="elk"
ELASTICSEARCH_SERVICE="${ELASTICSEARCH_RELEASE_NAME:-elasticsearch}-master"
ELASTICSEARCH_POD_SELECTOR="app=${ELASTICSEARCH_RELEASE_NAME:-elasticsearch}-master"
KIBANA_SERVICE="${KIBANA_RELEASE_NAME:-kibana}-kibana"
KIBANA_POD_SELECTOR="app=${KIBANA_RELEASE_NAME:-kibana}"
KAFKA_SERVICE="${KAFKA_RELEASE_NAME:-kafka}.elk.svc.cluster.local:9092"
KAFKA_TOPIC="competition1"
KAFKA_CLIENT_USER="user1"

CREDS_DIR="./kube_creds"
ES_CACERT_FILE="${CREDS_DIR}/elastic-ca.crt"
ES_PASSWORD_FILE="${CREDS_DIR}/es_password.txt"
KAFKA_PASSWORD_FILE="${CREDS_DIR}/kafka_user1_password.txt"

READONLY_USER="user"
READONLY_PASS="userPass456"
READONLY_ROLE="kibana_dashboard_only"

KUBECTL_TIMEOUT="2m"
WAIT_INTERVAL=10
MAX_RETRIES=12

# === Helper Functions ===
log_info() { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $1"; }
log_warn() { echo "[WARN] $(date '+%Y-%m-%d %H:%M:%S') - $1"; }
log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $1" >&2; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

get_pod_name() {
  local selector="$1"; local ns="$2"
  local pod_name
  pod_name=$(kubectl get pods -n "$ns" -l "$selector" -o jsonpath='{.items[?(@.status.phase=="Running")].metadata.name}' | awk '{print $1}')
  if [ -z "$pod_name" ]; then
    log_error "No running pod found with selector '$selector' in namespace '$ns'."
    return 1
  fi
  echo "$pod_name"
  return 0
}

exec_in_pod() {
  local pod_name="$1"; local ns="$2"; local container_name="${3:-}"; local command_to_run="$4"
  local container_arg=""
  if [ -n "$container_name" ]; then container_arg="-c $container_name"; fi
  log_info "Executing in pod '$pod_name' (ns: $ns): $command_to_run"
  if ! kubectl exec "$pod_name" -n "$ns" $container_arg -- bash -c "$command_to_run"; then
    log_error "Command failed in pod '$pod_name'."
    return 1
  fi
  return 0
}

wait_for_es_api() {
  local es_pod_name="$1"; local ns="$2"; local es_pass="$3"; local ca_path_in_pod="/tmp/elastic-ca.crt"; local retries=0
  log_info "Waiting for Elasticsearch API to be healthy via pod '$es_pod_name'..."
  log_info "Copying CA cert to pod '$es_pod_name:$ca_path_in_pod'..."
  if ! kubectl cp "$ES_CACERT_FILE" "${ns}/${es_pod_name}:${ca_path_in_pod}"; then
    log_error "Failed to copy CA cert to pod '$es_pod_name'."
    return 1
  fi
  local health_check_cmd="curl --cacert ${ca_path_in_pod} -s -u \"elastic:${es_pass}\" -k 'https://localhost:9200/_cluster/health?pretty' | grep -qE '\"status\"\\s*:\\s*\"(yellow|green)\"'"
  until exec_in_pod "$es_pod_name" "$ns" "" "$health_check_cmd"; do
    retries=$((retries + 1))
    if [ $retries -ge $MAX_RETRIES ]; then
      log_error "Elasticsearch API did not become healthy after $MAX_RETRIES attempts."
      exec_in_pod "$es_pod_name" "$ns" "" "rm -f ${ca_path_in_pod}" || log_warn "Failed to remove temp CA cert from pod."
      return 1
    fi
    log_info "Waiting for ES API... (Attempt $((retries+1))/$MAX_RETRIES)"
    sleep $WAIT_INTERVAL
  done
  exec_in_pod "$es_pod_name" "$ns" "" "rm -f ${ca_path_in_pod}" || log_warn "Failed to remove temp CA cert from pod."
  log_info "Elasticsearch API is healthy."
  return 0
}

wait_for_kibana_api() {
  local kibana_pod_name="$1"; local ns="$2"; local es_pass="$3"; local retries=0; local max_retries=$MAX_RETRIES
  log_info "Waiting for Kibana API to be ready in pod '$kibana_pod_name'..."
  until kubectl exec "$kibana_pod_name" -n "$ns" -- curl -s -o /dev/null -w "%{http_code}" -u elastic:"$es_pass" "http://localhost:5601/api/status" | grep -q "200"; do
    retries=$((retries + 1))
    if [ $retries -ge $max_retries ]; then
      log_error "Kibana API did not become ready after $max_retries attempts."
      return 1
    fi
    log_info "Waiting for Kibana API... (Attempt $retries/$max_retries)"
    sleep $WAIT_INTERVAL
  done
  log_info "Kibana API is ready."
  return 0
}

run_kafka_command_job() {
  local job_name="$1"; local kafka_command="$2"; local client_properties_content="$3"; local ns="$4"; local image="confluentinc/cp-kafka:latest"
  log_info "Creating Kafka client Job '$job_name' to run: $kafka_command"
  local configmap_name="${job_name}-props"
  kubectl create configmap "$configmap_name" --from-literal=client.properties="$client_properties_content" -n "$ns" --dry-run=client -o yaml | kubectl apply -f -
  cat <<EOF | kubectl apply -n "$ns" -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: $job_name
spec:
  ttlSecondsAfterFinished: 100
  template:
    spec:
      containers:
      - name: kafka-client
        image: $image
        command: ["/bin/sh", "-c"]
        args:
          - >
            echo "Running Kafka command...";
            $kafka_command;
            echo "Kafka command finished with exit code \$?.";
        volumeMounts:
        - name: client-props-volume
          mountPath: /tmp/config
      volumes:
      - name: client-props-volume
        configMap:
          name: $configmap_name
      restartPolicy: Never
  backoffLimit: 1
EOF
  log_info "Waiting for Job '$job_name' to complete..."
  if ! kubectl wait --for=condition=complete job/"$job_name" -n "$ns" --timeout=$KUBECTL_TIMEOUT; then
    log_error "Kafka client Job '$job_name' failed to complete."
    log_info "Job logs:"
    kubectl logs job/"$job_name" -n "$ns"
    kubectl delete job "$job_name" -n "$ns" --ignore-not-found=true
    kubectl delete configmap "$configmap_name" -n "$ns" --ignore-not-found=true
    return 1
  fi
  log_info "Kafka client Job '$job_name' completed successfully."
  log_info "Job logs:"
  kubectl logs job/"$job_name" -n "$ns"
  kubectl delete configmap "$configmap_name" -n "$ns" --ignore-not-found=true
  return 0
}

# === Pre-flight Checks ===
log_info "Performing pre-flight checks..."
for cmd in kubectl jq curl base64; do
  if ! command_exists "$cmd"; then
    log_error "Required command '$cmd' is not installed or not in PATH."
    exit 1
  fi
done
log_info "All required commands found."

if [ ! -f "$ES_PASSWORD_FILE" ] || [ ! -f "$ES_CACERT_FILE" ] || [ ! -f "$KAFKA_PASSWORD_FILE" ]; then
  log_error "Credential files not found in $CREDS_DIR. Please run './kube_deploy.sh' first."
  exit 1
fi

ES_PASSWORD=$(cat "$ES_PASSWORD_FILE")
KAFKA_PASSWORD=$(cat "$KAFKA_PASSWORD_FILE")

if [ -z "$ES_PASSWORD" ] || [ "$KAFKA_PASSWORD" == "PASSWORD_NOT_FOUND" ] || [ -z "$KAFKA_PASSWORD" ]; then
  log_error "Failed to load credentials from files in $CREDS_DIR."
  if [ "$KAFKA_PASSWORD" == "PASSWORD_NOT_FOUND" ]; then
    log_warn "Kafka password was not found during deployment. Kafka-related configuration steps will be skipped."
  else
    exit 1
  fi
fi
log_info "Credentials loaded successfully."

# --- Main Configuration ---
log_info "Starting Kubernetes ELK Stack Configuration..."

# 1. Find Elasticsearch Pod and Wait for API
log_info "Finding running Elasticsearch master pod..."
ES_POD_NAME=$(get_pod_name "$ELASTICSEARCH_POD_SELECTOR" "$NAMESPACE")
if [ $? -ne 0 ]; then exit 1; fi
log_info "Found Elasticsearch master pod: $ES_POD_NAME"
wait_for_es_api "$ES_POD_NAME" "$NAMESPACE" "$ES_PASSWORD"
if [ $? -ne 0 ]; then exit 1; fi

# 2. Configure Elasticsearch User and Role
log_info "Configuring Elasticsearch role '$READONLY_ROLE' and user '$READONLY_USER'..."
ES_CMD_BASE="curl --cacert /tmp/elastic-ca.crt -s -k -u elastic:${ES_PASSWORD} -H 'Content-Type: application/json'"
ES_URL_BASE="https://localhost:9200"
log_info "Copying CA cert to pod '$ES_POD_NAME:/tmp/elastic-ca.crt' for configuration..."
kubectl cp "$ES_CACERT_FILE" "${NAMESPACE}/${ES_POD_NAME}:/tmp/elastic-ca.crt"
ROLE_PAYLOAD=$(cat <<EOF | jq -c .
{
  "cluster": ["monitor"],
  "indices": [{ "names": ["*"], "privileges": ["read", "view_index_metadata"] }],
  "applications": [{ "application": "kibana-.kibana", "privileges": ["read"], "resources": ["*"] }]
}
EOF
)
create_role_cmd="${ES_CMD_BASE} -X PUT '${ES_URL_BASE}/_security/role/${READONLY_ROLE}' -d '${ROLE_PAYLOAD}' -o /dev/null -w '%{http_code}'"
http_code=$(kubectl exec "$ES_POD_NAME" -n "$NAMESPACE" -- bash -c "$create_role_cmd")
if [[ "$http_code" == "200" || "$http_code" == "201" ]]; then
  log_info "Elasticsearch role '$READONLY_ROLE' created/updated (HTTP $http_code)."
else
  log_error "Failed to create/update Elasticsearch role '$READONLY_ROLE' (HTTP $http_code)."
fi
USER_PAYLOAD=$(cat <<EOF | jq -c .
{
  "password": "${READONLY_PASS}",
  "roles": ["${READONLY_ROLE}"],
  "full_name": "Read-Only User (K8s)",
  "email": "readonly-k8s@example.com",
  "enabled": true
}
EOF
)
create_user_cmd="${ES_CMD_BASE} -X PUT '${ES_URL_BASE}/_security/user/${READONLY_USER}' -d '${USER_PAYLOAD}' -o /dev/null -w '%{http_code}'"
http_code=$(kubectl exec "$ES_POD_NAME" -n "$NAMESPACE" -- bash -c "$create_user_cmd")
if [[ "$http_code" == "200" || "$http_code" == "201" ]]; then
  log_info "Elasticsearch user '$READONLY_USER' created/updated (HTTP $http_code)."
else
  log_error "Failed to create/update Elasticsearch user '$READONLY_USER' (HTTP $http_code)."
fi

# 3. Check/Create Elasticsearch Index for Kafka Topic (new index)
log_info "Checking/Creating Elasticsearch index '$KAFKA_TOPIC'..."
check_index_cmd="${ES_CMD_BASE} -X GET '${ES_URL_BASE}/${KAFKA_TOPIC}' -o /dev/null -w '%{http_code}'"
http_code=$(kubectl exec "$ES_POD_NAME" -n "$NAMESPACE" -- bash -c "$check_index_cmd")
if [ "$http_code" == "200" ]; then
  log_info "Elasticsearch index '$KAFKA_TOPIC' already exists."
elif [ "$http_code" == "404" ]; then
  log_info "Elasticsearch index '$KAFKA_TOPIC' does not exist. Creating..."
  INDEX_PAYLOAD=$(cat <<EOF | jq -c .
{
  "settings": { "index.number_of_shards": 1, "index.number_of_replicas": 0 },
  "mappings": { "properties": { "@timestamp": { "type": "date" }, "message": { "type": "text" } } }
}
EOF
  )
  create_index_cmd="${ES_CMD_BASE} -X PUT '${ES_URL_BASE}/${KAFKA_TOPIC}' -d '${INDEX_PAYLOAD}' -o /dev/null -w '%{http_code}'"
  create_http_code=$(kubectl exec "$ES_POD_NAME" -n "$NAMESPACE" -- bash -c "$create_index_cmd")
  if [ "$create_http_code" == "200" ]; then
    log_info "Elasticsearch index '$KAFKA_TOPIC' created successfully."
  else
    log_error "Failed to create Elasticsearch index '$KAFKA_TOPIC' (HTTP $create_http_code)."
  fi
else
  log_error "Error checking Elasticsearch index '$KAFKA_TOPIC' (HTTP $http_code)."
fi
log_info "Removing temporary CA cert from ES pod '$ES_POD_NAME'..."
exec_in_pod "$ES_POD_NAME" "$NAMESPACE" "" "rm -f /tmp/elastic-ca.crt" || log_warn "Failed to remove temp CA cert from ES pod."

# 4. Configure Kibana Index Pattern (for competition1) with authentication
log_info "Finding running Kibana pod..."
KIBANA_POD_NAME=$(get_pod_name "$KIBANA_POD_SELECTOR" "$NAMESPACE")
if [ $? -ne 0 ]; then
  log_warn "Could not find running Kibana pod. Skipping Kibana index pattern setup."
else
  log_info "Found Kibana pod: $KIBANA_POD_NAME"
  log_info "Waiting for Kibana API to be ready..."
  if ! wait_for_kibana_api "$KIBANA_POD_NAME" "$NAMESPACE" "$ES_PASSWORD"; then
    log_error "Kibana API is not ready. Skipping index pattern creation."
  else
    log_info "Configuring Kibana index pattern for '$KAFKA_TOPIC'..."
    KIBANA_CMD_BASE="curl -s -u elastic:${ES_PASSWORD} -H 'kbn-xsrf: true' -H 'Content-Type: application/json'"
    KIBANA_URL_BASE="http://localhost:5601"
    KIBANA_PATTERN_PAYLOAD=$(cat <<EOF | jq -c .
{
  "attributes": {
    "title": "${KAFKA_TOPIC}",
    "timeFieldName": "@timestamp"
  }
}
EOF
    )
    kibana_pattern_cmd="${KIBANA_CMD_BASE} -X POST '${KIBANA_URL_BASE}/api/saved_objects/index-pattern' -d '${KIBANA_PATTERN_PAYLOAD}' -o /dev/null -w '%{http_code}'"
    retries=0
    while true; do
      http_code=$(kubectl exec "$KIBANA_POD_NAME" -n "$NAMESPACE" -- bash -c "$kibana_pattern_cmd")
      if [[ "$http_code" == "200" || "$http_code" == "201" ]]; then
        log_info "Kibana index pattern '$KAFKA_TOPIC' created successfully (HTTP $http_code)."
        break
      else
        retries=$((retries+1))
        if [ $retries -ge $MAX_RETRIES ]; then
          log_warn "Failed to create Kibana index pattern '$KAFKA_TOPIC' after $retries attempts (HTTP $http_code)."
          break
        fi
        log_info "Retrying Kibana index pattern creation... (Attempt $retries/$MAX_RETRIES)"
        sleep $WAIT_INTERVAL
      fi
    done
  fi
fi

# 5. Send Test Message to Kafka
if [ "$KAFKA_PASSWORD" != "PASSWORD_NOT_FOUND" ]; then
  log_info "Sending test message to Kafka topic '$KAFKA_TOPIC'..."
  CLIENT_PROPS=$(cat <<EOF
security.protocol=SASL_PLAINTEXT
sasl.mechanism=SCRAM-SHA-256
sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username="${KAFKA_CLIENT_USER}" password="${KAFKA_PASSWORD}";
EOF
  )
  TEST_MESSAGE="{\"@timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)\",\"message\":\"K8s Kafka-to-Logstash test message $(date)\"}"
  KAFKA_PRODUCER_CMD="echo '${TEST_MESSAGE}' | kafka-console-producer --bootstrap-server ${KAFKA_SERVICE} --topic ${KAFKA_TOPIC} --producer.config /tmp/config/client.properties"
  run_kafka_command_job "kafka-producer-test-$(date +%s)" "$KAFKA_PRODUCER_CMD" "$CLIENT_PROPS" "$NAMESPACE"
  if [ $? -ne 0 ]; then
    log_error "Failed to send test message to Kafka."
  else
    log_info "Test message sent to Kafka topic '$KAFKA_TOPIC'. Allow time for Logstash processing."
    sleep 15
  fi
else
  log_warn "Skipping Kafka test message send because Kafka password was not retrieved."
fi

# 6. Verify Test Message in Elasticsearch (search in index 'competition1')
log_info "Attempting to verify test message in Elasticsearch index '$KAFKA_TOPIC'..."
VERIFY_TARGET="${KAFKA_TOPIC}"
RAW_QUERY="message:\"K8s Kafka-to-Logstash test message\" AND NOT tags:\"_jsonparsefailure\""
VERIFY_QUERY_ENCODED=$(printf %s "$RAW_QUERY" | jq -sRr @uri)
VERIFY_URL_FULL="https://localhost:9200/${VERIFY_TARGET}/_search?q=${VERIFY_QUERY_ENCODED}&size=1&sort=@timestamp:desc&pretty"
log_info "Copying CA cert to pod '$ES_POD_NAME:/tmp/elastic-ca.crt' for verification..."
kubectl cp "$ES_CACERT_FILE" "${NAMESPACE}/${ES_POD_NAME}:/tmp/elastic-ca.crt"
log_info "Running search query in pod '$ES_POD_NAME'..."
search_output=$(kubectl exec "$ES_POD_NAME" -n "$NAMESPACE" -- \
  curl --cacert /tmp/elastic-ca.crt -s -k -u "elastic:${ES_PASSWORD}" -H 'Content-Type: application/json' \
  "${VERIFY_URL_FULL}")
log_info "Removing temporary CA cert from ES pod '$ES_POD_NAME' after verification..."
exec_in_pod "$ES_POD_NAME" "$NAMESPACE" "" "rm -f /tmp/elastic-ca.crt" || log_warn "Failed to remove temp CA cert after search."
if ! echo "$search_output" | jq -e . > /dev/null 2>&1; then
  log_error "Verification failed: Received invalid JSON output from Elasticsearch."
  log_error "Output was: $search_output"
  hit_count=0
else
  hit_count=$(echo "$search_output" | jq -r '.hits.total.value // 0')
fi
if [[ "$hit_count" -gt 0 ]]; then
  log_info "✔ Verification successful: Found test message(s) matching query in index '${VERIFY_TARGET}'."
  echo "$search_output" | jq '.hits.hits[0]'
else
  es_error=$(echo "$search_output" | jq -r '.error.reason // ""')
  if [[ -n "$es_error" ]]; then
    log_warn "⚠ Verification failed: Elasticsearch returned an error: $es_error"
    log_warn "   Full error response: $(echo "$search_output" | jq -c .)"
  else
    log_warn "⚠ Verification inconclusive: Test message not found in index '${VERIFY_TARGET}' yet."
    log_warn "   Possible reasons: Logstash delay, processing modifications, Kafka issue, or search query details."
    log_warn "   Search result snippet: $(echo "$search_output" | head -n 10)"
  fi
fi

log_info "--------------------------------------------------"
log_info "Configuration script finished."
log_info "Check Kibana and Elasticsearch for data."
log_info "You might need to manually set the Kibana index pattern if the automated step failed."
log_info "--------------------------------------------------"
exit 0

