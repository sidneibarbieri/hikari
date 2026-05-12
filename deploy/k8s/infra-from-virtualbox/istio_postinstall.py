import os
import subprocess
import time

def execute_command(command, capture_output=False):
    """Executes a shell command."""
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=capture_output, text=True)
        if capture_output:
            return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {command}\n{e}")
        exit(1)

def download_istio(version, target_arch):
    """Downloads Istio."""
    print("Downloading Istio...")
    command = f"curl -L https://istio.io/downloadIstio | ISTIO_VERSION={version} TARGET_ARCH={target_arch} sh -"
    execute_command(command)

def set_path(istio_dir):
    """Sets Istio binaries in the PATH."""
    print("Setting PATH...")
    istio_bin_path = os.path.join(istio_dir, "bin")
    os.environ["PATH"] += f":{istio_bin_path}"

def precheck_istio():
    """Performs Istio precheck."""
    print("Performing Istio precheck...")
    execute_command("istioctl x precheck")

def install_istio(profile):
    """Installs Istio."""
    print("Installing Istio...")
    command = f"istioctl install --set profile={profile} -y"
    execute_command(command)

def enable_namespace_injection(namespace):
    """Enables sidecar injection for a namespace."""
    print(f"Enabling sidecar injection for namespace {namespace}...")
    command = f"kubectl label namespace {namespace} istio-injection=enabled"
    execute_command(command)

def get_ingress_pod():
    """Gets the name of the Istio ingress gateway pod."""
    print("Retrieving Istio ingress gateway pod...")
    pods_output = execute_command("kubectl get pods -n istio-system", capture_output=True)
    for line in pods_output.splitlines():
        if "istio-ingressgateway" in line and "Running" in line:
            return line.split()[0]
    raise Exception("Ingress gateway pod not found!")

def proxy_config_routes(ingress_pod):
    """Displays proxy configuration routes for the ingress gateway."""
    print(f"Retrieving proxy config routes for pod {ingress_pod}...")
    command = f"istioctl proxy-config routes {ingress_pod} -n istio-system"
    routes = execute_command(command, capture_output=True)
    print("\nProxy Config Routes:\n")
    print(routes)

if __name__ == "__main__":
    ISTIO_VERSION = "1.24.2"
    TARGET_ARCH = "x86_64"
    ISTIO_DIR = f"istio-{ISTIO_VERSION}"
    NAMESPACE = "default"

    download_istio(ISTIO_VERSION, TARGET_ARCH)
    set_path(os.path.expanduser(f"~/cluster/{ISTIO_DIR}"))
    precheck_istio()
    install_istio("demo")
    enable_namespace_injection(NAMESPACE)

    print("Waiting for Istio pods to be ready...")
    time.sleep(30)  # Give some time for pods to start

    ingress_pod = get_ingress_pod()
    proxy_config_routes(ingress_pod)
