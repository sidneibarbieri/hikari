#!/bin/bash

# Download kubectl and its SHA256 checksum
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl.sha256"

# Verify the SHA256 checksum
echo "$(<kubectl.sha256) kubectl" | sha256sum --check

# Install kubectl using sudo and pass the password via the environment variable
echo "$SUDO_PASSWORD" | sudo -S install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

kubectl get nodes
kubectl get pods -A
