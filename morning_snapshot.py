#!/usr/bin/env python3
"""
morning_snapshot.py — Hosting Local Morning Data Collector
Queries Prometheus + Loki + Alertmanager for the past 24h and
pushes a structured JSON payload to ntfy topic hl-morning-data.

Run daily via systemd timer at 06:30 UTC (08:30 CEST) from networkserver.
"""
import json
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

PROMETHEUS = "http://192.168.111.18:9090"
LOKI       = "http://192.168.111.18:3100"
ALERTMGR   = "http://192.168.111.18:9093"
NTFY_URL   = "https://ntfy.hostinglocal.be/hl-morning-data"
NTFY_TOKEN = "tk_okm65mem9fj8by2w2w48uoz14j630"


def prom_query(query):
    url = f"{PROMETHEUS}/api/v1/query?query={urllib.parse.quote(query)}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.load(r).get("data", {}).get("result", [])
    except Exception as e:
        return [{"error": str(e)}]


def prom_range(query, hours=24, step="5m"):
    now = datetime.now(timezone.utc)
    start = (now - timedelta(hours=hours)).isoformat()
    end = now.isoformat()
    url = (f"{PROMETHEUS}/api/v1/query_range?"
           f"query={urllib.parse.quote(query)}&start={urllib.parse.quote(start)}"
           f"&end={urllib.parse.quote(end)}&step={step}")
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.load(r).get("data", {}).get("result", [])
    except Exception as e:
        return [{"error": str(e)}]


def get_alerts():
    url = f"{ALERTMGR}/api/v2/alerts?silenced=false&inhibited=false"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            alerts = json.load(r)
        result = []
        for a in alerts:
            result.append({
                "alertname": a.get("labels", {}).get("alertname", "?"),
                "severity":  a.get("labels", {}).get("severity", "?"),
                "instance":  a.get("labels", {}).get("instance", "?"),
                "job":       a.get("labels", {}).get("job", "?"),
                "since":     a.get("startsAt", "?"),
                "summary":   a.get("annotations", {}).get("summary", ""),
            })
        return result
    except Exception as e:
        return [{"error": str(e)}]


def get_loki_errors(hours=24):
    """Fetch last 50 error/critical lines from all Loki streams."""
    now_ns = int(datetime.now(timezone.utc).timestamp() * 1e9)
    start_ns = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp() * 1e9)
    logql = '{job=~".+"} |= "error" != "healthcheck" != "GET /metrics"'
    url = (f"{LOKI}/loki/api/v1/query_range?"
           f"query={urllib.parse.quote(logql)}"
           f"&start={start_ns}&end={now_ns}&limit=60&direction=backward")
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.load(r)
        streams = data.get("data", {}).get("result", [])
        lines = []
        for stream in streams:
            labels = stream.get("stream", {})
            host = labels.get("host", labels.get("job", "?"))
            for ts, line in stream.get("values", []):
                lines.append({"host": host, "line": line[:200]})
        return lines[:50]
    except Exception as e:
        return [{"error": str(e)}]


def max_over_24h(metric, label_filter=""):
    """Return max value seen per instance in last 24h."""
    results = prom_range(f"max_over_time({metric}{{{label_filter}}}[24h])")
    out = {}
    for r in results:
        if "error" in r:
            continue
        instance = r.get("metric", {}).get("instance", r.get("metric", {}).get("host", "?"))
        values = r.get("values", [])
        if values:
            try:
                out[instance] = round(float(values[-1][1]), 1)
            except Exception:
                pass
    return out


def collect():
    now = datetime.now(timezone.utc).isoformat()
    print(f"[{now}] Starting morning snapshot collection...", flush=True)

    # 1. Up/down status
    up_results = prom_query("up")
    up = {}
    down = []
    for r in up_results:
        if "error" in r:
            continue
        inst = r.get("metric", {}).get("instance", "?")
        val = r.get("value", [None, "0"])[1]
        if val == "1":
            up[inst] = True
        else:
            down.append({"instance": inst, "job": r.get("metric", {}).get("job", "?")})

    # 2. Active alerts
    alerts = get_alerts()
    critical = [a for a in alerts if a.get("severity") == "critical"]
    warnings  = [a for a in alerts if a.get("severity") == "warning"]

    # 3. Max CPU (%) per host in last 24h
    cpu_max = {}
    cpu_data = prom_range(
        '100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
        hours=24, step="10m"
    )
    for r in cpu_data:
        if "error" in r:
            break
        inst = r.get("metric", {}).get("instance", "?")
        vals = [float(v[1]) for v in r.get("values", []) if v[1] != "NaN"]
        if vals:
            cpu_max[inst] = round(max(vals), 1)

    # 4. Current memory usage (%) per host
    mem_results = prom_query(
        '100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))'
    )
    mem_now = {}
    for r in mem_results:
        if "error" in r:
            break
        inst = r.get("metric", {}).get("instance", "?")
        try:
            mem_now[inst] = round(float(r.get("value", [None, "0"])[1]), 1)
        except Exception:
            pass

    # 5. Disk usage (%) per host — top problematic
    disk_results = prom_query(
        '100 - (node_filesystem_avail_bytes{mountpoint="/",fstype!="tmpfs"} '
        '/ node_filesystem_size_bytes{mountpoint="/",fstype!="tmpfs"} * 100)'
    )
    disk_now = {}
    for r in disk_results:
        if "error" in r:
            break
        inst = r.get("metric", {}).get("instance", "?")
        try:
            val = round(float(r.get("value", [None, "0"])[1]), 1)
            if val > 60:
                disk_now[inst] = val
        except Exception:
            pass

    # 6. Temperature alerts (max over 24h)
    temp_results = prom_query('node_hwmon_temp_celsius{sensor="temp1"}')
    temps = {}
    for r in temp_results:
        if "error" in r:
            break
        inst = r.get("metric", {}).get("instance", "?")
        try:
            temps[inst] = round(float(r.get("value", [None, "0"])[1]), 1)
        except Exception:
            pass

    # 7. Loki errors
    loki_errors = get_loki_errors(hours=24)

    payload = {
        "collected_at": now,
        "period_hours": 24,
        "targets": {
            "up_count": len(up),
            "down": down,
        },
        "alerts": {
            "critical": critical,
            "warnings": warnings,
        },
        "performance": {
            "cpu_max_24h": dict(sorted(cpu_max.items(), key=lambda x: -x[1])[:15]),
            "memory_now": dict(sorted(mem_now.items(), key=lambda x: -x[1])[:15]),
            "disk_above_60pct": disk_now,
            "temperatures": temps,
        },
        "loki_errors": loki_errors,
    }

    return payload


def ntfy_post(topic, title, body, tags="bar_chart", priority="default"):
    url = f"https://ntfy.hostinglocal.be/{topic}"
    body_bytes = body.encode("utf-8")[:4000]
    req = urllib.request.Request(
        url,
        data=body_bytes,
        headers={
            "Authorization": f"Bearer {NTFY_TOKEN}",
            "Content-Type": "text/plain",
            "Title": title,
            "Tags": tags,
            "Priority": priority,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status


def push_to_ntfy(payload):
    ts = payload["collected_at"][:16].replace("T", " ") + " UTC"
    up  = payload["targets"]["up_count"]
    down = payload["targets"]["down"]
    crit = payload["alerts"]["critical"]
    warn = payload["alerts"]["warnings"]
    perf = payload["performance"]
    logs = payload["loki_errors"]

    # Message 1: header + alerts
    alert_lines = []
    for a in crit:
        alert_lines.append(f"  [CRITICAL] {a['alertname']} — {a['instance']}")
    for a in warn:
        alert_lines.append(f"  [warning]  {a['alertname']} — {a['instance']}")
    down_lines = [f"  DOWN: {d['instance']} ({d['job']})" for d in down]

    msg1 = (
        f"=== HOSTING LOCAL — {ts} ===\n"
        f"Targets: {up} up, {len(down)} down\n"
        f"Alerts:  {len(crit)} critical, {len(warn)} warnings\n\n"
        + ("CRITICAL:\n" + "\n".join(alert_lines[:5]) if crit else "Geen critical alerts")
        + ("\n\nDOWN TARGETS:\n" + "\n".join(down_lines) if down else "")
        + ("\n\nWARNINGS (top 5):\n" + "\n".join(alert_lines[:5]) if not crit and warn else "")
    )
    s1 = ntfy_post("hl-morning-data", f"HL Alerts ({len(crit)}c/{len(warn)}w)", msg1,
                   tags="rotating_light" if crit else "white_check_mark",
                   priority="high" if crit else "default")

    # Message 2: performance (top CPU + memory + disk)
    cpu = list(perf["cpu_max_24h"].items())[:8]
    mem = list(perf["memory_now"].items())[:8]
    disk = list(perf["disk_above_60pct"].items())
    temps = [(k, v) for k, v in perf["temperatures"].items() if v > 60]

    perf_lines = []
    if cpu:
        perf_lines.append("CPU max 24h (top):")
        perf_lines += [f"  {k}: {v}%" for k, v in cpu]
    if mem:
        perf_lines.append("Memory now (top):")
        perf_lines += [f"  {k}: {v}%" for k, v in mem]
    if disk:
        perf_lines.append("Disk >60%:")
        perf_lines += [f"  {k}: {v}%" for k, v in disk]
    if temps:
        perf_lines.append("Temperatures >60°C:")
        perf_lines += [f"  {k}: {v}°C" for k, v in temps]

    msg2 = "\n".join(perf_lines) if perf_lines else "Geen performance-issues"
    s2 = ntfy_post("hl-morning-data", "HL Performance", msg2)

    # Message 3: Loki errors (compact)
    if logs and "error" not in logs[0]:
        seen = {}
        for entry in logs:
            h = entry.get("host", "?")
            if h not in seen:
                seen[h] = []
            if len(seen[h]) < 3:
                seen[h].append(entry.get("line", "")[:120])
        loki_lines = []
        for host, lines in list(seen.items())[:8]:
            loki_lines.append(f"[{host}]")
            loki_lines += [f"  {l}" for l in lines]
        msg3 = "\n".join(loki_lines) if loki_lines else "Geen log-errors gevonden"
        err_count = len(logs)
    else:
        msg3 = "Loki niet bereikbaar of geen errors"
        err_count = 0

    s3 = ntfy_post("hl-morning-data", f"HL Logs ({err_count} errors)", msg3)

    return s1, s2, s3


if __name__ == "__main__":
    payload = collect()

    down_count = len(payload["targets"]["down"])
    crit_count = len(payload["alerts"]["critical"])
    warn_count = len(payload["alerts"]["warnings"])
    loki_count = len(payload["loki_errors"])

    print(f"Collected: {payload['targets']['up_count']} up, {down_count} down, "
          f"{crit_count} critical, {warn_count} warnings, {loki_count} log errors")

    s1, s2, s3 = push_to_ntfy(payload)
    print(f"ntfy push: alerts={s1}, perf={s2}, logs={s3}")
    sys.exit(0 if all(s == 200 for s in (s1, s2, s3)) else 1)
