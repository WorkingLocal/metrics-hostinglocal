#!/usr/bin/env python3
"""
NetBox Prometheus exporter — schrijft inventory counts naar textfile_collector.
Cron: */5 * * * * /usr/bin/python3 /opt/metrics-hostinglocal/scripts/netbox-exporter.py >> /tmp/netbox-exporter.log 2>&1
"""
import json
import time
import urllib.request
import os

NETBOX_URL = "http://192.168.111.63:8000"
NETBOX_TOKEN = "nbt_QFRmWaRtexnJ.RdsjrywP9VBQUjqn6CQTmsOTwgOO0d3TNLvTBqLw"
OUTPUT_FILE = "/var/lib/node_exporter/textfile_collector/netbox_inventory.prom"

ENDPOINTS = {
    "netbox_devices_total":            ("/api/dcim/devices/?limit=1",                     "Total number of devices in NetBox"),
    "netbox_ip_addresses_total":       ("/api/ipam/ip-addresses/?limit=1",                "Total number of IP addresses in NetBox"),
    "netbox_prefixes_total":           ("/api/ipam/prefixes/?limit=1",                    "Total number of IP prefixes in NetBox"),
    "netbox_virtual_machines_total":   ("/api/virtualization/virtual-machines/?limit=1",  "Total number of virtual machines in NetBox"),
    "netbox_cables_total":             ("/api/dcim/cables/?limit=1",                      "Total number of cables in NetBox"),
    "netbox_services_total":           ("/api/ipam/services/?limit=1",                    "Total number of services in NetBox"),
}

def fetch(path):
    req = urllib.request.Request(
        NETBOX_URL + path,
        headers={"Authorization": f"Token {NETBOX_TOKEN}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def main():
    start = time.time()
    lines = []
    success = 1

    for metric, (endpoint, help_text) in ENDPOINTS.items():
        try:
            count = fetch(endpoint).get("count", 0)
        except Exception as e:
            print(f"ERROR {metric}: {e}")
            count = 0
            success = 0
        lines.append(f"# HELP {metric} {help_text}")
        lines.append(f"# TYPE {metric} gauge")
        lines.append(f"{metric} {count}")

    duration = time.time() - start
    lines += [
        "# HELP netbox_scrape_success 1 if last NetBox scrape was successful",
        "# TYPE netbox_scrape_success gauge",
        f"netbox_scrape_success {success}",
        "# HELP netbox_scrape_duration_seconds Duration of last NetBox scrape in seconds",
        "# TYPE netbox_scrape_duration_seconds gauge",
        f"netbox_scrape_duration_seconds {duration:.3f}",
    ]

    tmp = OUTPUT_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, OUTPUT_FILE)
    print(f"OK — {duration:.2f}s, success={success}")

if __name__ == "__main__":
    main()
