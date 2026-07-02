#!/usr/bin/env python3
"""NTFY per-topic Prometheus metrics exporter (textfile_collector).

Queryt de NTFY API voor elk geconfigureerd topic en telt berichten
per tijdsperiode. Schrijft metrics naar textfile_collector zodat
node_exporter ze oppikt.

Config via environment variabelen:
  NTFY_URL      = http://100.125.153.71:2586
  NTFY_TOKEN    = tk_...
  NTFY_TOPICS   = homelab,backup,ha  (kommagescheiden)
  NTFY_PROM_OUT = /var/lib/node_exporter/textfile_collector/ntfy.prom
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

NTFY_URL   = os.environ.get("NTFY_URL",    "http://100.125.153.71:2586").rstrip("/")
NTFY_TOKEN = os.environ.get("NTFY_TOKEN",  "tk_okm65mem9fj8by2w2w48uoz14j630")
TOPICS     = [t.strip() for t in os.environ.get("NTFY_TOPICS", "hl-critical,hl-uptime,hl-warning,hl-backup,hl-resolved,wl-uptime").split(",") if t.strip()]
PROM_OUT   = os.environ.get("NTFY_PROM_OUT",
             "/var/lib/node_exporter/textfile_collector/ntfy.prom")

PERIODS = [("1h", "1h"), ("24h", "24h"), ("7d", "168h")]

PRIORITY_NAMES = {1: "min", 2: "low", 3: "default", 4: "high", 5: "urgent"}


def fetch_messages(topic: str, since: str) -> list[dict]:
    """Haal berichten op voor topic via ntfy poll API."""
    url = f"{NTFY_URL}/{topic}/json?since={since}&poll=1"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {NTFY_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            messages = []
            for line in resp:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if obj.get("event") == "message":
                        messages.append(obj)
                except json.JSONDecodeError:
                    pass
            return messages
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} voor {topic} since={since}: {e.reason}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Fout voor {topic} since={since}: {e}", file=sys.stderr)
        return []


def main():
    ts = int(time.time())
    lines = [
        "# HELP ntfy_topic_message_count Berichten per topic per periode (gauge)",
        "# TYPE ntfy_topic_message_count gauge",
        "# HELP ntfy_topic_message_count_by_priority Berichten per topic/periode/prioriteit",
        "# TYPE ntfy_topic_message_count_by_priority gauge",
        "# HELP ntfy_exporter_last_run_timestamp Unix timestamp van laatste exporter run",
        "# TYPE ntfy_exporter_last_run_timestamp gauge",
        f"ntfy_exporter_last_run_timestamp {ts}",
    ]

    for topic in TOPICS:
        for period_label, since in PERIODS:
            msgs = fetch_messages(topic, since)
            count = len(msgs)
            lines.append(
                f'ntfy_topic_message_count{{topic="{topic}",period="{period_label}"}} {count}'
            )

            # teller per prioriteit
            prio_counts: dict[int, int] = {}
            for m in msgs:
                p = m.get("priority", 3)
                prio_counts[p] = prio_counts.get(p, 0) + 1
            for prio, cnt in sorted(prio_counts.items()):
                pname = PRIORITY_NAMES.get(prio, str(prio))
                lines.append(
                    f'ntfy_topic_message_count_by_priority{{topic="{topic}",period="{period_label}",priority="{pname}"}} {cnt}'
                )

    prom_content = "\n".join(lines) + "\n"
    with open(PROM_OUT, "w", encoding="utf-8") as f:
        f.write(prom_content)

    print(f"[ntfy-exporter] {len(TOPICS)} topic(s), geschreven naar {PROM_OUT}")


if __name__ == "__main__":
    main()
