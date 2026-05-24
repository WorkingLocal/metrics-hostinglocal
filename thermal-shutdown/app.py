import json
import logging
import os
import time
from datetime import datetime

import paramiko
import yaml
from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SSH_KEY_PATH = os.getenv("SSH_KEY_PATH", "/app/keys/id_ed25519")
HOSTS_FILE = os.getenv("HOSTS_FILE", "/app/hosts.yml")

with open(HOSTS_FILE) as f:
    HOSTS_CONFIG = yaml.safe_load(f)

# Tracks recent shutdowns to prevent duplicate triggers: {instance: timestamp}
_shutdown_log: dict[str, float] = {}
COOLDOWN_SECONDS = 3600  # 1 uur cooldown per host


def _already_shutdown(instance: str) -> bool:
    last = _shutdown_log.get(instance)
    if last and (time.time() - last) < COOLDOWN_SECONDS:
        return True
    return False


def shutdown_host(instance: str) -> tuple[bool, str]:
    if _already_shutdown(instance):
        msg = f"Shutdown reeds uitgevoerd voor {instance} binnen cooldown window"
        logger.warning(msg)
        return False, msg

    host_cfg = HOSTS_CONFIG.get("hosts", {}).get(instance)
    if not host_cfg:
        return False, f"Geen SSH configuratie voor instance '{instance}'"

    ip = host_cfg["tailscale_ip"]
    user = host_cfg["ssh_user"]
    port = host_cfg.get("ssh_port", 22)
    cmd = host_cfg.get("shutdown_cmd", 'shutdown -h +1 "Thermal shutdown via Prometheus alert"')
    logger.info(f"Graceful shutdown starten: {instance} ({user}@{ip}:{port})")

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, port=port, username=user, key_filename=SSH_KEY_PATH, timeout=10)
        _, stdout, stderr = ssh.exec_command(cmd)
        exit_code = stdout.channel.recv_exit_status()
        ssh.close()

        if exit_code == 0:
            _shutdown_log[instance] = time.time()
            logger.info(f"Shutdown commando verzonden naar {instance}")
            return True, "shutdown commando verzonden"
        else:
            err = stderr.read().decode().strip()
            logger.error(f"Shutdown mislukt op {instance}: {err}")
            return False, err

    except Exception as exc:
        logger.error(f"SSH verbinding mislukt voor {instance}: {exc}")
        return False, str(exc)


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    logger.info(f"Webhook ontvangen: {json.dumps(data)}")

    results = []
    for alert in data.get("alerts", []):
        status = alert.get("status")
        labels = alert.get("labels", {})
        alertname = labels.get("alertname", "")
        instance = labels.get("instance", "")
        action = labels.get("action", "")

        if status == "firing" and action == "shutdown" and instance:
            ok, msg = shutdown_host(instance)
            results.append({"instance": instance, "success": ok, "message": msg})
        elif status == "resolved":
            logger.info(f"Alert resolved: {alertname} op {instance}")

    return jsonify({"results": results})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9095)
