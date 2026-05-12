#!/bin/bash
set -e

# Fetch Kafka password from the secret in the 'elk' namespace
KAFKA_SASL_PASSWORD=$(kubectl get secret kafka-user-passwords --namespace elk -o jsonpath='{.data.client-passwords}' | base64 -d | cut -d , -f 1)
export KAFKA_SASL_PASSWORD

echo "Fetched Kafka SASL password."

# Substitute the environment variable in the template and create the actual ConfigMap file
envsubst < ctfd-configmap-template.yaml > ctfd-configmap.yaml

# Deploy the namespace and then all YAML files in the directory
kubectl apply -f ctfd-namespace.yaml
kubectl apply -f .

echo "Deployment applied. Current pods in namespace ctfd:"
kubectl get pods -n ctfd

