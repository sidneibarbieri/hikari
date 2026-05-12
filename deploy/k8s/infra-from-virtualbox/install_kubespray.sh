\#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

# Clone the Kubespray repository
if [ ! -d "kubespray" ]; then
  git clone https://github.com/kubernetes-sigs/kubespray.git
fi

cd kubespray

# Copy inventory configuration
cp -rfp inventory/sample inventory/mycluster
cp ../inventory.ini inventory/mycluster/inventory.ini

# Set up a virtual environment
VENVDIR=kubespray-venv
if [ ! -d "$VENVDIR" ]; then
  python3 -m venv $VENVDIR
fi

# Activate the virtual environment
# Use . instead of source for compatibility
. $VENVDIR/bin/activate

# Install dependencies with --break-system-packages if needed
pip install -U -r requirements.txt

# Verify connection to the nodes
ansible -i inventory/mycluster/inventory.ini kube_node -m ping --private-key ~/.ssh/id_rsa_root -u root

# Run the Kubespray playbook
ansible-playbook -i inventory/mycluster/inventory.ini cluster.yml -b -v --private-key ~/.ssh/id_rsa_root -u root
