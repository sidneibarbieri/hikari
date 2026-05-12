import os
import subprocess
import time
from functools import wraps

def time_function(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"Function '{func.__name__}' took {end_time - start_time:.2f} seconds.")
        return result
    return wrapper

@time_function
def wait_for_machines():
    for _ in range(10):
        result = subprocess.run(["vagrant", "status", "--machine-readable"], capture_output=True, text=True)
        lines = result.stdout.splitlines()
        machines = list(set([
            line.split(",")[1] for line in lines
            if "state" in line and "running" in line and not line.split(",")[1].startswith("ui") and line.split(",")[1].strip()
        ]))
        if machines:
            return machines
        time.sleep(5)
    print("Error: Machines are not running after waiting.")
    return []

@time_function
def fetch_machine_ips(machines):
    machine_ips = {}
    for machine in machines:
        try:
            ip_result = subprocess.run(
                [
                    "vagrant", "ssh", machine, "-c",
                    "ip addr show eth1 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1"
                ],
                capture_output=True, text=True, timeout=15
            )
            ip_address = ip_result.stdout.strip()
            if ip_address:
                machine_ips[machine] = ip_address
            else:
                print(f"Warning: No IP address found for {machine}. Skipping.")
        except subprocess.TimeoutExpired:
            print(f"Error: Timeout while fetching IP for {machine}. Skipping.")
        except Exception as e:
            print(f"Error: Unable to fetch IP for {machine}: {e}")
    return machine_ips

@time_function
def generate_ssh_key():
    key_path = os.path.expanduser("~/.ssh/id_rsa_root")
    if not os.path.exists(key_path):
        subprocess.run(["ssh-keygen", "-t", "rsa", "-b", "2048", "-f", key_path, "-N", ""], check=True)
        print(f"SSH key generated at {key_path}.")
    else:
        print(f"SSH key already exists at {key_path}.")
    return key_path

@time_function
def copy_ssh_key_to_root(machine_ips, key_path):
    public_key_path = f"{key_path}.pub"
    with open(public_key_path, "r") as pub_key_file:
        public_key = pub_key_file.read().strip()

    for machine, ip_address in machine_ips.items():
        try:
            subprocess.run(
                [
                    "vagrant", "ssh", machine, "-c",
                    f"echo '{public_key}' | sudo tee -a /root/.ssh/authorized_keys && sudo chmod 600 /root/.ssh/authorized_keys"
                ],
                check=True
            )
            print(f"SSH key copied to root user on {machine} ({ip_address}).")
        except Exception as e:
            print(f"Error: Unable to configure SSH for {machine}: {e}")

@time_function
def test_ssh_connectivity(machine_ips, key_path):
    for machine, ip_address in machine_ips.items():
        try:
            ssh_result = subprocess.run(
                ["ssh", "-i", key_path, "-o", "StrictHostKeyChecking=no", f"root@{ip_address}", "echo 'SSH connectivity test'"],
                capture_output=True, text=True
            )
            if ssh_result.returncode == 0:
                print(f"Passwordless SSH to {machine} ({ip_address}) works.")
            else:
                print(f"Failed SSH test to {machine} ({ip_address}): {ssh_result.stderr}")
        except Exception as e:
            print(f"Error: Unable to test SSH for {machine}: {e}")

@time_function
def generate_inventory_file(machine_ips):
    inventory_file = "inventory.ini"

    # Sort machines by name for consistent assignment of control plane nodes
    sorted_machines = sorted(machine_ips.items(), key=lambda x: x[0])
    control_plane_nodes = sorted_machines[:3]  # Use first 3 nodes as control plane
    remaining_nodes = sorted_machines[3:]

    with open(inventory_file, "w") as inventory:
        inventory.write("[kube_control_plane]\n")
        for i, (machine, ip_address) in enumerate(control_plane_nodes, start=1):
            inventory.write(f"{machine} ansible_host={ip_address} ip={ip_address} etcd_member_name=etcd{i}\n")

        inventory.write("\n[etcd:children]\n")
        inventory.write("kube_control_plane\n")

        inventory.write("\n[kube_node]\n")
        for machine, ip_address in sorted_machines:
            inventory.write(f"{machine} ansible_host={ip_address} ip={ip_address}\n")

        inventory.write("\n[k8s_cluster:children]\n")
        inventory.write("kube_control_plane\n")
        inventory.write("kube_node\n")

    print(f"Inventory file '{inventory_file}' generated.")

@time_function
def generate_inventory():
    machines = wait_for_machines()
    if machines:
        machine_ips = fetch_machine_ips(machines)
        key_path = generate_ssh_key()
        copy_ssh_key_to_root(machine_ips, key_path)
        test_ssh_connectivity(machine_ips, key_path)
        generate_inventory_file(machine_ips)

if __name__ == "__main__":
    generate_inventory()
