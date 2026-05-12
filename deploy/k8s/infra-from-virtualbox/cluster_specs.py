import yaml
import psutil
from collections import OrderedDict
from yaml.representer import SafeRepresenter

# Helper function to represent OrderedDict as a normal YAML dictionary
class OrderedDumper(yaml.SafeDumper):
    pass

def represent_ordered_dict(dumper, data):
    return dumper.represent_dict(data.items())

OrderedDumper.add_representer(OrderedDict, represent_ordered_dict)

def get_physical_machine_specs():
    """
    Retrieve the physical machine's total RAM and CPU cores.
    """
    total_ram = int(psutil.virtual_memory().total / (1024 ** 2))  # Convert bytes to MB
    total_cpus = psutil.cpu_count(logical=True)  # Total logical CPUs
    return total_ram, total_cpus

def calculate_vms(total_ram, total_cpus, reserved_ram, reserved_cpus, vm_ram):
    """
    Calculate the maximum number of VMs and ensure CPU cores are even.

    :param total_ram: Total RAM of the physical machine (in MB)
    :param total_cpus: Total CPU cores of the physical machine
    :param reserved_ram: RAM reserved for the base OS (in MB)
    :param reserved_cpus: CPU cores reserved for the base OS
    :param vm_ram: RAM per VM (in MB)
    :return: Number of VMs, per-VM specs (RAM and CPUs)
    """
    available_ram = total_ram - reserved_ram
    available_cpus = total_cpus - reserved_cpus

    max_vms_by_ram = available_ram // vm_ram
    num_vms = max_vms_by_ram

    # Ensure even CPU cores are distributed
    max_vms_by_cpu = available_cpus // 2  # Each VM gets a minimum of 2 cores (even)
    num_vms = min(num_vms, max_vms_by_cpu)

    # Calculate CPUs per VM (must be even)
    cores_per_vm = (available_cpus // num_vms) // 2 * 2  # Round down to nearest even number

    return num_vms, cores_per_vm

def generate_cluster_config(num_vms, vm_ram, vm_cpus, vm_box):
    """
    Generate a YAML configuration for a cluster of VMs.

    :param num_vms: Number of VMs
    :param vm_ram: RAM per VM (in MB)
    :param vm_cpus: Number of CPUs per VM
    :param vm_box: Default Vagrant box for each VM
    :return: YAML configuration as a dictionary
    """
    config = {'vms': []}

    for i in range(1, num_vms + 1):
        vm_name = f"node{i:02}"  # Ensure two decimal places for node names
        has_disk = i > num_vms - 2  # Add a disk only to the last two VMs
        config['vms'].append(OrderedDict([
            ('name', vm_name),
            ('memory', vm_ram),
            ('cpus', vm_cpus),
            ('box', vm_box),
            ('disk', has_disk)  # Add disk flag
        ]))

    return config

def save_config_to_yaml(config, filename):
    """
    Save the generated configuration to a YAML file.

    :param config: Cluster configuration dictionary
    :param filename: Output YAML file name
    """
    with open(filename, 'w') as yaml_file:
        yaml.dump(config, yaml_file, default_flow_style=False, sort_keys=False, Dumper=OrderedDumper)

if __name__ == "__main__":
    # Base OS reserved resources
    reserved_ram = 4096  # 4GB in MB
    reserved_cpus = 2    # 2 CPUs

    # VM configuration
    vm_ram = 8192  # 8GB in MB (fixed RAM per VM)
    vm_box = "gutehall/ubuntu24-10"  # Default Vagrant box
    total_ram, total_cpus = get_physical_machine_specs()

    # Calculate the number of VMs and distribute CPUs evenly
    num_vms, cores_per_vm = calculate_vms(
        total_ram, total_cpus, reserved_ram, reserved_cpus, vm_ram
    )

    if num_vms < 1 or cores_per_vm < 2:
        print("\nInsufficient resources to create any VMs. Exiting.")
    else:
        print(f"\nThe physical machine can support {num_vms} VMs with:")
        print(f"- {vm_ram} MB RAM per VM")
        print(f"- {cores_per_vm} CPU cores per VM (even number)")
        print(f"- {vm_box} Vagrant box per VM")

        # Generate and save the configuration
        cluster_config = generate_cluster_config(num_vms, vm_ram, cores_per_vm, vm_box)
        save_config_to_yaml(cluster_config, 'cluster_config.yaml')
        print("\nYAML configuration file 'cluster_config.yaml' has been created.")
