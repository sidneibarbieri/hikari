import yaml
import subprocess

def get_running_nodes():
    try:
        result = subprocess.run(["vagrant", "status"], capture_output=True, text=True)
        lines = result.stdout.splitlines()
        nodes = [line.split()[0] for line in lines if "running" in line]
        return nodes
    except Exception as e:
        print(f"Error getting vagrant status: {e}")
        return []

def generate_rook_ceph_yaml(nodes):
    if len(nodes) < 2:
        raise ValueError("At least two nodes are required to configure RookFS.")

    rook_ceph_config = {
        "apiVersion": "ceph.rook.io/v1",
        "kind": "CephCluster",
        "metadata": {
            "name": "rook-ceph",
            "namespace": "rook-ceph"
        },
        "spec": {
            "cephVersion": {
                "image": "quay.io/ceph/ceph:v19.2.0",
                "allowUnsupported": False
            },
            "dataDirHostPath": "/var/lib/rook",
            "skipUpgradeChecks": False,
            "continueUpgradeAfterChecksEvenIfNotHealthy": False,
            "waitTimeoutForHealthyOSDInMinutes": 10,
            "upgradeOSDRequiresHealthyPGs": False,
            "mon": {
                "count": 3,
                "allowMultiplePerNode": False
            },
            "mgr": {
                "count": 2,
                "allowMultiplePerNode": False,
                "modules": [
                    {"name": "rook", "enabled": True}
                ]
            },
            "dashboard": {
                "enabled": True,
                "ssl": True
            },
            "monitoring": {
                "enabled": False,
                "metricsDisabled": False,
                "exporter": {
                    "perfCountersPrioLimit": 5,
                    "statsPeriodSeconds": 5
                }
            },
            "network": {
                "connections": {
                    "encryption": {"enabled": False},
                    "compression": {"enabled": False},
                    "requireMsgr2": False
                }
            },
            "crashCollector": {"disable": False},
            "logCollector": {
                "enabled": True,
                "periodicity": "daily",
                "maxLogSize": "500M"
            },
            "cleanupPolicy": {
                "confirmation": "",
                "sanitizeDisks": {
                    "method": "quick",
                    "dataSource": "zero",
                    "iteration": 1
                },
                "allowUninstallWithVolumes": False
            },
            "annotations": None,
            "labels": None,
            "resources": None,
            "removeOSDsIfOutAndSafeToRemove": False,
            "priorityClassNames": {
                "mon": "system-node-critical",
                "osd": "system-node-critical",
                "mgr": "system-cluster-critical"
            },
            "storage": {
                "useAllNodes": False,
                "useAllDevices": False,
                "nodes": [
                    {"name": nodes[-2], "devices": [{"name": "sdb"}]},
                    {"name": nodes[-1], "devices": [{"name": "sdb"}]}
                ],
                "onlyApplyOSDPlacement": False
            },
            "disruptionManagement": {
                "managePodBudgets": True,
                "osdMaintenanceTimeout": 30,
                "pgHealthCheckTimeout": 0
            },
            "csi": {
                "readAffinity": {
                    "enabled": False
                },
                "cephfs": None
            },
            "healthCheck": {
                "daemonHealth": {
                    "mon": {"disabled": False, "interval": "45s"},
                    "osd": {"disabled": False, "interval": "60s"},
                    "status": {"disabled": False, "interval": "60s"}
                },
                "livenessProbe": {
                    "mon": {"disabled": False},
                    "mgr": {"disabled": False},
                    "osd": {"disabled": False}
                },
                "startupProbe": {
                    "mon": {"disabled": False},
                    "mgr": {"disabled": False},
                    "osd": {"disabled": False}
                }
            }
        }
    }

    with open("rook_ceph_cluster.yaml", "w") as yaml_file:
        yaml.dump(rook_ceph_config, yaml_file, default_flow_style=False, sort_keys=False)
    print("rook_ceph_cluster.yaml generated successfully.")

if __name__ == "__main__":
    running_nodes = get_running_nodes()
    generate_rook_ceph_yaml(running_nodes)
