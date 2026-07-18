import json
import logging
import os
import time
from datetime import datetime

import requests
import yaml
from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HOSTS_FILE = os.getenv("HOSTS_FILE", "/app/hosts.yml")
POWER_CONTROL_PRIMARY = os.getenv("POWER_CONTROL_PRIMARY", "http://100.103.226.56:8765")
POWER_CONTROL_BACKUP = os.getenv("POWER_CONTROL_BACKUP", "http://100.97.195.23:8765")

with open(HOSTS_FILE) as f:
    HOSTS_CONFIG = yaml.safe_load(f)
INSTANCE_MAP: dict = HOSTS_CONFIG.get("instance_map", {})

# Tracks recent actions to prevent duplicate triggers: {"shutdown:<host>": timestamp}
_action_log: dict[str, float] = {}
SHUTDOWN_COOLDOWN_SECONDS = 3600   # destructief, lange dedup-window
COOLDOWN_COOLDOWN_SECONDS = 600    # niet-destructief, mag vaker herhalen als temp blijft schommelen
RESET_COOLDOWN_SECONDS = 30        # enkel dubbele gelijktijdige "resolved"-webhooks dempen


def _recently_triggered(key: str, window: int) -> bool:
    last = _action_log.get(key)
    return bool(last and (time.time() - last) < window)


def call_power_control(endpoint: str, dedup_key: str, dedup_window: int) -> tuple[bool, str]:
    """POST naar power-control (FANSERVER primair, NUT-SERVER backup) i.p.v. zelf SSH te doen —
    power-control kent de VM/LXC-graceful-evacuatie per host, hier hoeft dat niet gedupliceerd."""
    if _recently_triggered(dedup_key, dedup_window):
        msg = f"Actie reeds uitgevoerd voor {dedup_key} binnen cooldown window"
        logger.warning(msg)
        return False, msg

    for base_url in (POWER_CONTROL_PRIMARY, POWER_CONTROL_BACKUP):
        try:
            resp = requests.post(f"{base_url}{endpoint}", timeout=15)
            if resp.ok:
                _action_log[dedup_key] = time.time()
                logger.info(f"{endpoint} -> {base_url} succeeded: {resp.text[:300]}")
                return True, resp.text[:300]
            logger.warning(f"{endpoint} -> {base_url} returned {resp.status_code}: {resp.text[:300]}")
        except Exception as exc:
            logger.warning(f"{endpoint} -> {base_url} unreachable: {exc}")

    return False, f"Both power-control instances unreachable/failed for {endpoint}"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    logger.info(f"Webhook ontvangen: {json.dumps(data)}")

    results = []
    for alert in data.get("alerts", []):
        status = alert.get("status")
        labels = alert.get("labels", {})
        instance = labels.get("instance", "")
        action = labels.get("action", "")

        if status != "firing" or action != "shutdown" or not instance:
            if status == "resolved":
                logger.info(f"Alert resolved: {labels.get('alertname', '')} op {instance}")
            continue

        pc_host = INSTANCE_MAP.get(instance)
        if not pc_host:
            logger.warning(f"Geen power-control mapping voor instance '{instance}'")
            results.append({"instance": instance, "success": False, "message": "no power-control mapping"})
            continue

        # force=true: een kritieke temperatuur-alert overrules power-control's always_on-bescherming
        # (die enkel per-ongeluk-shutdown via het dashboard voorkomt, geen echte thermische noodstop)
        ok, msg = call_power_control(f"/api/shutdown/{pc_host}?force=true", f"shutdown:{pc_host}", SHUTDOWN_COOLDOWN_SECONDS)
        results.append({"instance": instance, "power_control_host": pc_host, "success": ok, "message": msg})

    return jsonify({"results": results})


@app.route("/cooldown", methods=["POST"])
def cooldown():
    data = request.json
    logger.info(f"Cooldown webhook ontvangen: {json.dumps(data)}")

    results = []
    for alert in data.get("alerts", []):
        status = alert.get("status")
        labels = alert.get("labels", {})
        instance = labels.get("instance", "")
        action = labels.get("action", "")

        if action != "cooldown" or not instance or status not in ("firing", "resolved"):
            continue

        pc_host = INSTANCE_MAP.get(instance)
        if not pc_host:
            logger.warning(f"Geen power-control mapping voor instance '{instance}'")
            results.append({"instance": instance, "success": False, "message": "no power-control mapping"})
            continue

        if status == "firing":
            ok, msg = call_power_control(f"/api/cooldown/{pc_host}", f"cooldown:{pc_host}", COOLDOWN_COOLDOWN_SECONDS)
        else:
            ok, msg = call_power_control(f"/api/cooldown-reset/{pc_host}", f"cooldown-reset:{pc_host}", RESET_COOLDOWN_SECONDS)

        results.append({"instance": instance, "power_control_host": pc_host, "status": status, "success": ok, "message": msg})

    return jsonify({"results": results})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9095)
