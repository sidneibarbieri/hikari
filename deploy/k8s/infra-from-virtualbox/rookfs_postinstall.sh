#!/bin/bash

set -e

# Function to wait for a specific pod to be in Running state
wait_for_specific_pod_running() {
    local namespace=$1
    local pod_pattern=$2
    local timeout=$3 # Timeout in seconds
    local interval=10 # Check interval in seconds
    local elapsed=0

    echo "Waiting for pod matching '$pod_pattern' in namespace '$namespace' to be in Running state (timeout: $timeout seconds)..."
    while true; do
        POD=$(kubectl get pods -n "$namespace" --no-headers | grep "$pod_pattern" | awk '$3 == "Running" {print $1}')
        if [[ -n "$POD" ]]; then
            echo "Pod '$POD' in namespace '$namespace' is in Running state."
            break
        fi

        if [ "$elapsed" -ge "$timeout" ]; then
            echo "Timeout reached while waiting for pod '$pod_pattern' in namespace '$namespace'."
            echo "Current pod state:"
            kubectl get pods -n "$namespace" | grep "$pod_pattern"
            exit 1
        fi

        echo "Waiting for pod '$pod_pattern' to be in Running state... (Elapsed: $elapsed seconds)"
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done
}

# Clone the Rook repository
echo "Cloning the Rook repository..."
git clone https://github.com/rook/rook.git
cd rook/deploy/examples

# Deploy Rook CRDs, common resources, and operator
echo "Deploying Rook CRDs, common resources, and operator..."
kubectl create -f crds.yaml -f common.yaml -f operator.yaml
cd ../../..

# Generate the Rook Ceph cluster YAML configuration
echo "Generating the Rook Ceph cluster configuration..."
python3 generate_rook_yaml.py

# Deploy the Rook Ceph cluster
echo "Deploying the Rook Ceph cluster..."
kubectl create -f rook_ceph_cluster.yaml

# Wait for the specific Rook-Ceph OSD pod to be running
wait_for_specific_pod_running "rook-ceph" "rook-ceph-osd-0" 1200 # 1200 seconds (20 minutes) timeout

# Deploy the Rook toolbox
echo "Deploying the Rook toolbox..."
kubectl create -f rook/deploy/examples/toolbox.yaml

# Apply the StorageClass to applications
echo "Applying the StorageClass to applications..."
kubectl apply -f storageclass.yaml
