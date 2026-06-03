#!/usr/bin/env python3
# PBS (Proxmox Backup Server) Prometheus exporter
# Queries PBS REST API and writes metrics to textfile_collector
# Credentials read from /etc/metrics/pbs_token (format: user@pbs!tokenid:secret)

import urllib.request, urllib.error, json, ssl, os, sys, time

PBS_URL = "https://192.168.111.201:8007"
TOKEN_FILE = "/home/metrics/.config/metrics/pbs_token"
PROM_FILE = "/var/lib/node_exporter/textfile_collector/pbs_backup.prom"

def load_token():
    try:
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    except Exception as e:
        print(f"Cannot read token from {TOKEN_FILE}: {e}", file=sys.stderr)
        sys.exit(1)

def api_get(path, token):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(f"{PBS_URL}{path}")
    req.add_header("Authorization", f"PBSAPIToken={token}")
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=15)
        return json.loads(resp.read())
    except Exception as e:
        print(f"API error {path}: {e}", file=sys.stderr)
        return None

def write_metrics(lines):
    tmp = PROM_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.rename(tmp, PROM_FILE)

def main():
    token = load_token()
    now = int(time.time())
    lines = []

    # Datastore usage
    lines.append("# HELP pbs_datastore_available_bytes Free bytes in PBS datastore")
    lines.append("# TYPE pbs_datastore_available_bytes gauge")
    lines.append("# HELP pbs_datastore_used_bytes Used bytes in PBS datastore")
    lines.append("# TYPE pbs_datastore_used_bytes gauge")
    lines.append("# HELP pbs_datastore_total_bytes Total bytes in PBS datastore")
    lines.append("# TYPE pbs_datastore_total_bytes gauge")

    usage = api_get("/api2/json/status/datastore-usage", token)
    if usage and "data" in usage:
        for ds in usage["data"]:
            name = ds.get("store", "unknown")
            avail = ds.get("avail", 0)
            used = ds.get("used", 0)
            total = ds.get("total", 0)
            lines.append(f'pbs_datastore_available_bytes{{datastore="{name}"}} {avail}')
            lines.append(f'pbs_datastore_used_bytes{{datastore="{name}"}} {used}')
            lines.append(f'pbs_datastore_total_bytes{{datastore="{name}"}} {total}')

    # Recent backup tasks (last 24h)
    lines.append("# HELP pbs_backup_task_last_status 1=OK 0=error for most recent backup per VM+datastore")
    lines.append("# TYPE pbs_backup_task_last_status gauge")
    lines.append("# HELP pbs_backup_task_last_timestamp Unix timestamp of most recent backup task")
    lines.append("# TYPE pbs_backup_task_last_timestamp gauge")
    lines.append("# HELP pbs_backup_task_last_duration_seconds Duration of most recent backup task")
    lines.append("# TYPE pbs_backup_task_last_duration_seconds gauge")

    since = now - 7 * 24 * 3600
    tasks = api_get(f"/api2/json/nodes/localhost/tasks?start=0&limit=500&since={since}&typefilter=backup", token)

    # Track most recent task per (vmid, store)
    best = {}
    if tasks and "data" in tasks:
        for t in tasks["data"]:
            vmid = str(t.get("id", "unknown"))
            store = t.get("store", t.get("worker_id", "unknown"))
            # worker_id looks like "backup/ct/100/ds1" — extract parts
            if "/" in store:
                parts = store.split("/")
                vmid = parts[2] if len(parts) > 2 else vmid
                store = parts[3] if len(parts) > 3 else parts[-1]
            key = (vmid, store)
            ts = t.get("starttime", 0)
            if key not in best or ts > best[key]["starttime"]:
                best[key] = t

    for (vmid, store), t in best.items():
        status = t.get("status", "")
        success = 1 if status == "OK" else 0
        ts = t.get("starttime", 0)
        duration = t.get("duration", 0) or 0
        labels = f'vmid="{vmid}",datastore="{store}"'
        lines.append(f"pbs_backup_task_last_status{{{labels}}} {success}")
        lines.append(f"pbs_backup_task_last_timestamp{{{labels}}} {ts}")
        lines.append(f"pbs_backup_task_last_duration_seconds{{{labels}}} {duration}")

    lines.append(f"# HELP pbs_exporter_last_run_timestamp When the exporter last ran successfully")
    lines.append(f"# TYPE pbs_exporter_last_run_timestamp gauge")
    lines.append(f"pbs_exporter_last_run_timestamp {now}")

    write_metrics(lines)
    print(f"PBS metrics written to {PROM_FILE} ({len(lines)} lines)")

if __name__ == "__main__":
    main()
