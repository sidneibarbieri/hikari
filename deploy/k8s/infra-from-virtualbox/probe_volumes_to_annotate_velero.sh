#!/bin/bash

# Check if a namespace argument is provided
if [ $# -eq 0 ]; then
  echo "Usage: $0 <namespace>"
  exit 1
fi

namespace=$1
echo "Processing namespace: $namespace"

# Get all pods in the specified namespace
pods=$(kubectl get pod -n $namespace -o jsonpath='{.items[*].metadata.name}')

if [ -z "$pods" ]; then
  echo "No pods found in namespace: $namespace"
  exit 0
fi

for pod in $pods; do
  echo "  Pod: $pod"
  
  # Extract volumes and mount points
  kubectl get pod $pod -n $namespace -o json | jq -r '
    .spec.volumes[]? as $volume |
    select($volume.persistentVolumeClaim != null) |
    {
      pvc: $volume.persistentVolumeClaim.claimName,
      mountPath: (.spec.containers[].volumeMounts[]? |
                  select(.name == $volume.name) |
                  .mountPath)
    }' | jq -c '. | select(.pvc != null and .mountPath != null)' | while read -r line; do
    pvc=$(echo "$line" | jq -r '.pvc')
    mountPath=$(echo "$line" | jq -r '.mountPath')

    if [ -n "$pvc" ] && [ -n "$mountPath" ]; then
      echo "    PVC: $pvc, MountPath: $mountPath"
      echo "Annotating pod $pod with mount path $mountPath"
      echo "kubectl annotate pod $pod -n $namespace backup.velero.io/backup-volumes=$mountPath --overwrite"
      #kubectl annotate pod $pod -n $namespace backup.velero.io/backup-volumes=$mountPath --overwrite
    fi
  done
done
