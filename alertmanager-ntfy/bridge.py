Alertmanager → ntfy bridge.
Ontvangt Alertmanager webhook JSON, stuurt per alert een ntfy push.
"""
import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

NTFY_URL   = os.getenv("NTFY_URL", "http://ntfy:80")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "homelab")
NTFY_TOKEN = os.getenv("NTFY_TOKEN", "")

PRIORITY = {"critical": "5", "warning": "3"}
EMOJI    = {"critical": "🔥", "warning": "⚠️", "resolved": "✅"}

@app.route("/hook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    for alert in data.get("alerts", []):
        status   = alert.get("status", "unknown")
        name     = alert["labels"].get("alertname", "Alert")
        instance = alert["labels"].get("instance", "unknown")
        severity = alert["labels"].get("severity", "warning")
        desc     = alert["annotations"].get("description",
                   f"{name} op {instance}")

        if status == "resolved":
            title    = f"✅ [OPGELOST] {name}"
            priority = "2"
            tags     = "white_check_mark"
        else:
            emoji    = EMOJI.get(severity, "⚠️")
            title    = f"{emoji} {name} — {instance}"
            priority = PRIORITY.get(severity, "3")
            tags     = f"{severity},warning"

        requests.post(
            f"{NTFY_URL}/{NTFY_TOPIC}",
            json={
                "message":  desc,
                "title":    title,
                "priority": int(priority),
                "tags":     tags.split(","),
            },
            headers={"Authorization": f"Bearer {NTFY_TOKEN}"},
            timeout=5,
        )
    return jsonify({"status": "ok"}), 200

@app.route("/health")
def health():
    return "OK"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9095)
