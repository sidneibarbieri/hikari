import subprocess
import time
from threading import Timer

def run_command(command, timeout=None):
    """
    Run a shell command with optional timeout.
    """
    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)
        if timeout:
            timer = Timer(timeout, lambda p: p.kill(), [proc])
            timer.start()
        stdout, stderr = proc.communicate()
        if timeout:
            timer.cancel()
        return proc.returncode, stdout, stderr
    except Exception as e:
        return 1, "", f"Error running command: {e}"

def run_script(script_name):
    """
    Run a script and display real-time output.
    """
    print(f"Running {script_name}...")
    try:
        proc = subprocess.Popen(f"./{script_name}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in iter(proc.stdout.readline, ""):
            print(line.strip())
        proc.wait()
        if proc.returncode != 0:
            print(f"Error in {script_name}:\n{proc.stderr.read()}")
            exit(1)
        print(f"{script_name} completed successfully.")
    except Exception as e:
        print(f"Error during {script_name}: {e}")
        exit(1)

def run_cluster_specs():
    print("Running cluster_specs.py...")
    returncode, stdout, stderr = run_command("python3 cluster_specs.py")
    if returncode != 0:
        print(f"Error in cluster_specs.py:\n{stderr}")
        exit(1)
    print(stdout)
    print("cluster_specs.py completed successfully.")

def vagrant_up():
    print("Running vagrant up...")
    try:
        proc = subprocess.Popen("vagrant up", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in iter(proc.stdout.readline, ""):
            print(line.strip())
        proc.wait()
        if proc.returncode != 0:
            print("vagrant up failed. Destroying VMs...")
            subprocess.run("vagrant destroy -f", shell=True)
            exit(1)
        print("vagrant up completed successfully.")
    except Exception as e:
        print(f"Error during vagrant up: {e}")
        subprocess.run("vagrant destroy -f", shell=True)
        exit(1)

def run_generate_inventory():
    print("Running generate_inventory.py...")
    try:
        proc = subprocess.Popen("python3 generate_inventory.py", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in iter(proc.stdout.readline, ""):
            print(line.strip())
        proc.wait()
        if proc.returncode != 0:
            print(f"Error in generate_inventory.py:\n{proc.stderr.read()}")
            exit(1)
        print("generate_inventory.py completed successfully.")
    except Exception as e:
        print(f"Error during generate_inventory.py: {e}")
        exit(1)

def install_kubespray():
    print("Running install_kubespray.sh...")
    run_script("install_kubespray.sh")

def get_k8s_creds():
    print("Running get_k8s_creds.sh...")
    run_script("get_k8s_creds.sh")

def install_kubectl():
    print("Running install_kubectl.sh...")
    run_script("install_kubectl.sh")
    print("Verifying cluster with kubectl...")
    returncode, stdout, stderr = run_command("kubectl get nodes")
    if returncode != 0:
        print(f"Error running kubectl commands:\n{stderr}")
        exit(1)
    print(stdout)

if __name__ == "__main__":
    run_cluster_specs()
    vagrant_up()
    run_generate_inventory()
    install_kubespray()
    get_k8s_creds()
    install_kubectl()
    print("Cluster orchestration completed successfully.")
