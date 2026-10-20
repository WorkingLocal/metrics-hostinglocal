#!/usr/bin/env python3
"""Tailscale node-key vervaldata als Prometheus textfile-metrics.

Aanleiding: op 18/10/2026 verliep de key van vm-apps -> Vaultwarden (via cloudflared
naar Tailscale-IP) gaf 502, zonder dat iets waarschuwde. Keys verlopen na 180 dagen.

Metrics (label node):
  tailscale_node_key_days_left            dagen tot verval (negatief = verlopen); ontbreekt als verval uit staat
  tailscale_node_key_expired              1 als Tailscale de key als verlopen markeert
  tailscale_node_key_expiry_disabled      1 als sleutelverval is uitgezet
  tailscale_node_online                   1 als de node online is
  tailscale_keys_last_success_timestamp_seconds
Alleen nodes die online zijn of de laatste 45 dagen gezien zijn (oude restanten zouden eeuwig alarmeren).
Draait als cron (metrics-user); `tailscale status --json` heeft geen root nodig.
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time

OUT = os.environ.get("TS_KEYS_OUT", "/var/lib/node_exporter/textfile_collector/tailscale_keys.prom")
MAX_AGE_DAYS = 45
# Nodes die bewust zijn uitgefaseerd of geen echte machine zijn
EXCLUDE = {"localhost", "VPS-WORKINGLOCAL"}


def parse(ts):
    if not ts or ts.startswith("0001"):
        return None
    # oudere Python-versies accepteren geen fractie van 1-5 cijfers: weglaten (seconden volstaan)
    ts = re.sub(r"\.\d+", "", ts).replace("Z", "+00:00")
    return dt.datetime.fromisoformat(ts)


def main():
    raw = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=30)
    if raw.returncode != 0:
        print("tailscale status faalde:", raw.stderr.strip(), file=sys.stderr)
        return 1
    data = json.loads(raw.stdout)
    now = dt.datetime.now(dt.timezone.utc)
    nodes = list(data.get("Peer", {}).values())
    if data.get("Self"):
        nodes.append(data["Self"])

    lines = [
        "# HELP tailscale_node_key_days_left Dagen tot de Tailscale node-key verloopt (negatief = verlopen).",
        "# TYPE tailscale_node_key_days_left gauge",
    ]
    days, expired, disabled, online = [], [], [], []
    for p in nodes:
        name = p.get("HostName") or "?"
        if name in EXCLUDE:
            continue
        on = bool(p.get("Online"))
        seen = parse(p.get("LastSeen"))
        if not on and (seen is None or (now - seen).days > MAX_AGE_DAYS):
            continue
        exp = parse(p.get("KeyExpiry"))
        lab = 'node="%s"' % name.replace('"', "")
        online.append('tailscale_node_online{%s} %d' % (lab, 1 if on else 0))
        if exp is None:
            disabled.append('tailscale_node_key_expiry_disabled{%s} 1' % lab)
            continue
        left = (exp - now).total_seconds() / 86400
        days.append('tailscale_node_key_days_left{%s} %.2f' % (lab, left))
        expired.append('tailscale_node_key_expired{%s} %d' % (lab, 1 if (p.get("Expired") or left < 0) else 0))

    lines += sorted(days)
    lines += ["# TYPE tailscale_node_key_expired gauge"] + sorted(expired)
    lines += ["# TYPE tailscale_node_key_expiry_disabled gauge"] + sorted(disabled)
    lines += ["# TYPE tailscale_node_online gauge"] + sorted(online)
    lines += ["# TYPE tailscale_keys_last_success_timestamp_seconds gauge",
              "tailscale_keys_last_success_timestamp_seconds %d" % time.time()]

    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
