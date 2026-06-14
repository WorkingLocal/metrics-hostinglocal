"""
Alertmanager → ntfy webhook bridge.
Luistert op :9095/hook voor Alertmanager alerts.
Luistert op :9095/unifi-hook voor UniFi Network Application events.
"""
import os
import json
import logging
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

NTFY_URL   = os.environ["NTFY_URL"].rstrip("/")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "homelab")
NTFY_TOKEN = os.environ.get("NTFY_TOKEN", "")

PRIORITY_MAP = {
    "critical": 5,   # urgent
    "warning":  3,   # default
    "info":     2,   # low
}

TAG_MAP = {
    "critical": ["rotating_light"],
    "warning":  ["warning"],
    "resolved": ["white_check_mark"],
}


def _send(title: str, message: str, priority: int, tags: list[str], resolved: bool = False):
    headers = {
        "Title":    title,
        "Priority": str(priority),
        "Tags":     ",".join(tags),
    }
    if NTFY_TOKEN:
        headers["Authorization"] = f"Bearer {NTFY_TOKEN}"

    url = f"{NTFY_URL}/{NTFY_TOPIC}"
    try:
        r = requests.post(url, data=message.encode(), headers=headers, timeout=10)
        r.raise_for_status()
        logging.info("ntfy OK %s — %s", r.status_code, title)
    except Exception as exc:
        logging.error("ntfy FOUT: %s", exc)


@app.route("/hook", methods=["POST"])
def hook():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "geen JSON"}), 400

    for alert in data.get("alerts", []):
        status   = alert.get("status", "firing")
        labels   = alert.get("labels", {})
        annots   = alert.get("annotations", {})
        severity = labels.get("severity", "warning")
        name     = labels.get("alertname", "Alert")
        instance = labels.get("instance", "")

        if status == "resolved":
            title    = f"[HERSTELD] {name}"
            priority = 2
            tags     = TAG_MAP["resolved"]
        else:
            title    = f"[{severity.upper()}] {name}"
            priority = PRIORITY_MAP.get(severity, 3)
            tags     = TAG_MAP.get(severity, ["bell"])

        summary = annots.get("summary", "")
        desc    = annots.get("description", "")
        parts   = [p for p in [instance, summary, desc] if p]
        message = "\n".join(parts) if parts else name

        _send(title, message, priority, tags, resolved=(status == "resolved"))

    return jsonify({"status": "ok"}), 200


_UNIFI_CRITICAL = {"Lost_Contact", "Restart", "Disconnected", "IDS", "Honeypot"}

_UNIFI_PRIORITY = {
    "critical": 5,
    "warning": 3,
    "info": 2,
}

_UNIFI_TAGS = {
    "critical": ["rotating_light"],
    "warning": ["warning"],
    "info": ["bell"],
}


def _unifi_severity(key: str) -> str:
    key_upper = key.upper()
    if any(c in key_upper for c in ("LOST_CONTACT", "RESTART", "IDS_", "HONEYPOT")):
        return "critical"
    if any(c in key_upper for c in ("EVT_AP_", "EVT_SW_", "EVT_GW_", "EVT_UGW_")):
        return "warning"
    return "info"


@app.route("/unifi-hook", methods=["POST"])
def unifi_hook():
    """
    Accepteert UniFi Network Application webhook events.
    UniFi stuurt JSON met variabel formaat — probeer alle bekende velden.
    Webhook URL op UDM: http://192.168.111.18:9095/unifi-hook
    """
    data = request.get_json(force=True) or {}
    logging.info("UniFi webhook ontvangen: %s", json.dumps(data)[:500])

    # Normaliseer de payload: UniFi gebruikt wisselende structuren
    payload = data.get("payload") or data.get("data") or data
    key     = (data.get("key") or payload.get("key") or data.get("event") or "UNKNOWN").upper()
    msg     = payload.get("msg") or payload.get("message") or key
    ap_name = payload.get("ap_name") or payload.get("device_name") or ""

    severity = _unifi_severity(key)
    priority = _UNIFI_PRIORITY[severity]
    tags     = _UNIFI_TAGS[severity]

    title   = f"[UniFi] {key.replace('EVT_', '').replace('_', ' ').title()}"
    body    = f"{ap_name}\n{msg}".strip() if ap_name else msg

    _send(title, body, priority, tags)
    return jsonify({"status": "ok"}), 200


@app.route("/ntfy-messages")
def ntfy_messages():
    """Geeft recente ntfy berichten terug als JSON array voor Grafana Infinity."""
    import datetime
    since = request.args.get("since", "12h")
    try:
        headers = {}
        if NTFY_TOKEN:
            headers["Authorization"] = f"Bearer {NTFY_TOKEN}"
        r = requests.get(
            f"{NTFY_URL}/{NTFY_TOPIC}/json",
            params={"poll": "1", "since": since},
            headers=headers,
            timeout=10,
        )
        r.raise_for_status()
        messages = []
        for line in r.text.strip().splitlines():
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
                if msg.get("event") != "message":
                    continue
                ts = msg.get("time", 0)
                dt_str = datetime.datetime.utcfromtimestamp(ts).strftime("%d/%m %H:%M")
                messages.append({
                    "time": dt_str,
                    "title": msg.get("title", ""),
                    "message": msg.get("message", ""),
                    "priority": msg.get("priority", 3),
                    "tags": ",".join(msg.get("tags", [])),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        messages.sort(key=lambda m: m["time"], reverse=True)
        return jsonify(messages[:50])
    except Exception as exc:
        logging.error("ntfy-messages fout: %s", exc)
        return jsonify([]), 200


@app.route("/health")
def health():
    return jsonify({"healthy": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9095)
