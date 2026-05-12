#!/bin/bash

# Get the IP address of the node using vagrant
ip1=$(vagrant ssh node01 -c "ip addr show eth1" 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 | sed -r 's/\x1B\[[0-9;]*[a-zA-Z]//g')

# Ensure the IP address is obtained
if [ -z "$ip1" ]; then
  echo "Error: Unable to retrieve IP address for node01."
  exit 1
fi

# Define the remote admin.conf path
remote_admin_conf="/etc/kubernetes/admin.conf"

# Define the local destination for the kubeconfig
local_kubeconfig="$HOME/.kube/config"

# Create the .kube directory in the home directory if it doesn't exist
mkdir -p "$HOME/.kube"

# Copy admin.conf from the remote node to the local machine
echo "Fetching $remote_admin_conf from $ip1..."
scp -i ~/.ssh/id_rsa_root "root@$ip1:$remote_admin_conf" "$local_kubeconfig"

# Verify if the file was copied
if [ $? -ne 0 ]; then
  echo "Error: Failed to copy $remote_admin_conf from $ip1."
  exit 2
fi

# Update the kubeconfig to replace localhost with the node's IP address
echo "Updating kubeconfig with node IP: $ip1..."
sed -i "s/127\\.0\\.0\\.1/$ip1/g" "$local_kubeconfig"

# Confirm completion
echo "Kubeconfig updated and saved to $local_kubeconfig"

