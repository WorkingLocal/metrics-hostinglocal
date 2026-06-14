"""
Deploy script — Metrics Stack naar METRICSSERVER
Uploadt alle bestanden via SFTP en start de Docker stack.

Vereisten:
    pip install paramiko

Credentials:
    SSH wachtwoord: Vaultwarden → Homelab - Infrastructure → METRICSSERVER SSH
    Of zet METRICS_SSH_PASS als environment variabele.
"""
import paramiko, sys, time, os

LOCAL_REPO = os.path.dirname(os.path.abspath(__file__))
REMOTE_DIR = "/opt/metrics-hostinglocal"
HOST = "100.67.19.40"  # Tailscale IP (192.168.111.18 niet bereikbaar vanop laptop-VLAN)
USER = "metrics"
PASS = os.environ.get("METRICS_SSH_PASS") or input("SSH wachtwoord METRICSSERVER: ")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, look_for_keys=False, allow_agent=False)
print(f"Verbonden met {HOST}")

def run(cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(
        f"echo '{PASS}' | sudo -S bash -c \"{cmd}\"", timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    result = "\n".join(l for l in (out+"\n"+err).splitlines()
                       if l.strip() and "[sudo]" not in l and "password for" not in l.lower())
    if result:
        sys.stdout.buffer.write((result+"\n").encode("utf-8", "replace"))
        sys.stdout.buffer.flush()
    return out

run(f"mkdir -p {REMOTE_DIR}")
run(f"chown {USER}:{USER} {REMOTE_DIR}")

sftp = client.open_sftp()

def sftp_mkdir(path):
    try:
        sftp.mkdir(path)
    except Exception:
        pass

def upload_dir(local_path, remote_path):
    sftp_mkdir(remote_path)
    for item in sorted(os.listdir(local_path)):
        lp = os.path.join(local_path, item)
        rp = remote_path + "/" + item
        if os.path.isdir(lp):
            upload_dir(lp, rp)
        else:
            try:
                sftp.put(lp, rp)
                print(f"  {rp}")
            except Exception as e:
                print(f"  SKIP {rp}: {e}")

files = [
    "compose.hostinglocal.yml",
    "prometheus.hostinglocal.yml",
    "prometheus.yml",
    "alert.rules.yml",
    "alertmanager.yml",
]
dirs = ["grafana", "thermal-shutdown", "alertmanager-ntfy", "snmp", "kiosk", "scripts", "unifi"]

print(f"\nUploaden naar {REMOTE_DIR}...")
for f in files:
    lp = os.path.join(LOCAL_REPO, f)
    if os.path.exists(lp):
        sftp.put(lp, f"{REMOTE_DIR}/{f}")
        print(f"  {f}")

for d in dirs:
    lp = os.path.join(LOCAL_REPO, d)
    if os.path.exists(lp):
        upload_dir(lp, f"{REMOTE_DIR}/{d}")

# .env bijwerken — ontbrekende vars toevoegen, bestaande behouden
env_defaults = {
    "GRAFANA_ADMIN_PASSWORD": "",    # zie Vaultwarden
    "SMTP_PASSWORD": "",             # Hostinger SMTP
    "NTFY_PUBLISHER_TOKEN": "",      # zie Vaultwarden
    "NTFY_URL": "http://100.125.153.71:2586",
    "UNIFI_POLLER_USER": "",         # lokale UniFi admin (no SSO) — zie Vaultwarden
    "UNIFI_POLLER_PASS": "",         # lokale UniFi admin password
}
try:
    existing = sftp.open(f"{REMOTE_DIR}/.env", "r").read().decode("utf-8")
except Exception:
    existing = ""
existing_keys = {line.split("=")[0] for line in existing.splitlines() if "=" in line}
new_lines = existing.rstrip()
for k, v in env_defaults.items():
    if k not in existing_keys:
        new_lines += f"\n{k}={v}"
with sftp.open(f"{REMOTE_DIR}/.env", "w") as f:
    f.write(new_lines + "\n")
print("  .env")

sftp.close()

run(f"chown -R {USER}:{USER} {REMOTE_DIR}")

print("\nDocker netwerken...")
run("docker network create proxy 2>/dev/null || true")
run("docker network create metrics_internal 2>/dev/null || true")

print("\nStack starten...")
run(f"cd {REMOTE_DIR} && docker compose -f compose.hostinglocal.yml up -d 2>&1", 180)

# Prometheus bind-mount inode fix: altijd herstarten na config upload
# SFTP overschrijft het bestand met een nieuw inode; Docker ziet de stale versie
# tenzij de container herstart wordt.
print("\nPrometheus herstarten (inode fix)...")
run("docker restart prometheus-metrics", 30)

# Exporter scripts uitvoerbaar maken
print("\nScripts uitvoerbaar maken...")
run(f"chmod +x {REMOTE_DIR}/scripts/*.py 2>/dev/null || true")

# Cron jobs instellen (idempotent — bestaande regels overschrijven)
print("\nCron jobs instellen...")
cron_cmd = (
    f"(crontab -u {USER} -l 2>/dev/null | grep -v 'netbox-exporter\\|litellm-exporter\\|ntfy-exporter' || true; "
    f"echo '*/5 * * * * /usr/bin/python3 {REMOTE_DIR}/scripts/netbox-exporter.py >> /tmp/netbox-exporter.log 2>&1'; "
    f"echo '*/5 * * * * /usr/bin/python3 {REMOTE_DIR}/scripts/litellm-exporter.py >> /tmp/litellm-exporter.log 2>&1'; "
    f"echo '*/5 * * * * /usr/bin/python3 {REMOTE_DIR}/scripts/ntfy-exporter.py >> /tmp/ntfy-exporter.log 2>&1') "
    f"| crontab -u {USER} -"
)
run(cron_cmd)
run(f"crontab -u {USER} -l")

time.sleep(12)
print("\nContainer status:")
run("docker ps --format 'table {{.Names}}\\t{{.Status}}'")

client.close()
print("\n=== KLAAR ===")
print(f"Prometheus: http://192.168.111.18:9090  (of http://{HOST}:9090 via Tailscale)")
print(f"Grafana:    http://metrics.hostinglocal.be")
print(f"\n--- KIOSK SETUP (eenmalig, vereist reboot) ---")
print(f"SSH naar METRICSSERVER en voer uit:")
print(f"  sudo bash {REMOTE_DIR}/kiosk/setup.sh")
print(f"  sudo reboot")
print(f"Daarna opent Chromium automatisch na reboot.")
