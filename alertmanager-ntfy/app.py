"""
Alertmanager → ntfy webhook bridge.
Luistert op :9095/hook, stuurt alerts naar ntfy.
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


@app.route("/health")
def health():
    return jsonify({"healthy": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9095)
