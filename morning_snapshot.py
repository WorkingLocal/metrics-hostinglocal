#!/usr/bin/env python3
"""
morning_snapshot.py — Hosting Local Morning Data Collector
Queries Prometheus + Loki + Alertmanager for the past 24h and
pushes structured data to ntfy topic hl-morning-data (4 messages).

Run daily via systemd timer at 04:30 UTC (06:30 CEST) from networkserver.
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


def prom_range(query, hours=24, step="10m"):
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
    now_ns = int(datetime.now(timezone.utc).timestamp() * 1e9)
    start_ns = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp() * 1e9)
    logql = '{job=~".+"} |= "error" != "healthcheck" != "GET /metrics" != "GET /api/health"'
    url = (f"{LOKI}/loki/api/v1/query_range?"
           f"query={urllib.parse.quote(logql)}"
           f"&start={start_ns}&end={now_ns}&limit=80&direction=backward")
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
        return lines[:60]
    except Exception as e:
        return [{"error": str(e)}]


def get_pbs_status():
    results = prom_query("pbs_backup_task_last_status")
    ok, failed = [], []
    for r in results:
        if "error" in r:
            return None, None
        guest = r.get("metric", {}).get("guest", "?")
        try:
            status = int(float(r.get("value", [None, "0"])[1]))
            (ok if status == 1 else failed).append(guest)
        except Exception:
            pass
    return ok, failed


def get_pbs_ages():
    """Return guests whose last backup is older than 26h (missed a nightly run)."""
    results = prom_query("pbs_backup_task_last_timestamp")
    now_ts = datetime.now(timezone.utc).timestamp()
    stale = []
    for r in results:
        if "error" in r:
            break
        guest = r.get("metric", {}).get("guest", "?")
        try:
            ts = float(r.get("value", [None, "0"])[1])
            age_h = (now_ts - ts) / 3600
            if age_h > 26:
                stale.append(f"{guest} ({age_h:.0f}u geleden)")
        except Exception:
            pass
    return stale


def get_energy():
    power = prom_query("homeassistant_sensor_power_w")
    energy = prom_query("homeassistant_sensor_energy_kwh")
    # UPS extra sensors
    ups_load = prom_query('homeassistant_sensor_percentage_percent{entity=~".*eatonups.*load.*"}')
    ups_battery = prom_query('homeassistant_sensor_percentage_percent{entity=~".*eatonups.*batt.*"}')
    ups_runtime = prom_query('homeassistant_sensor_second_s{entity=~".*eatonups.*runtime.*"}')

    result = {}
    for r in power:
        if "error" in r:
            break
        name = r.get("metric", {}).get("friendly_name", "")
        try:
            val = round(float(r.get("value", [None, "0"])[1]), 1)
        except Exception:
            continue
        if "Beem" in name and "Current Power" in name:
            result["solar_w"] = val
        elif "EatonUPS Real power" in name or "Eaton" in name and "power" in name.lower():
            result["ups_w"] = val

    for r in energy:
        if "error" in r:
            break
        name = r.get("metric", {}).get("friendly_name", "")
        try:
            val = round(float(r.get("value", [None, "0"])[1]), 2)
        except Exception:
            continue
        if "Beem" in name and "Totaal" in name:
            result["solar_kwh_total"] = val
        elif "Homelab" in name and "kWh" in name:
            result["homelab_kwh_total"] = val

    for r in ups_load:
        if "error" not in r:
            try:
                result["ups_load_pct"] = round(float(r.get("value", [None, "0"])[1]), 1)
            except Exception:
                pass
    for r in ups_battery:
        if "error" not in r:
            try:
                result["ups_battery_pct"] = round(float(r.get("value", [None, "0"])[1]), 1)
            except Exception:
                pass
    for r in ups_runtime:
        if "error" not in r:
            try:
                result["ups_runtime_min"] = round(float(r.get("value", [None, "0"])[1]) / 60, 0)
            except Exception:
                pass
    return result


def get_recent_reboots(hours=24):
    """Hosts that rebooted within the last N hours (boot_time is recent)."""
    results = prom_query("node_boot_time_seconds")
    now_ts = datetime.now(timezone.utc).timestamp()
    rebooted = []
    for r in results:
        if "error" in r:
            break
        inst = r.get("metric", {}).get("instance", "?")
        try:
            boot_ts = float(r.get("value", [None, "0"])[1])
            age_h = (now_ts - boot_ts) / 3600
            if age_h < hours:
                rebooted.append(f"{inst} ({age_h:.1f}u geleden)")
        except Exception:
            pass
    return rebooted


def collect():
    now = datetime.now(timezone.utc).isoformat()
    print(f"[{now}] Starting morning snapshot collection...", flush=True)

    # 1. Up/down status
    up_results = prom_query("up")
    up, down = {}, []
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

    # 3. CPU max per host in last 24h
    cpu_max = {}
    for r in prom_range('100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'):
        if "error" in r:
            break
        inst = r.get("metric", {}).get("instance", "?")
        vals = [float(v[1]) for v in r.get("values", []) if v[1] not in ("NaN", "+Inf")]
        if vals:
            cpu_max[inst] = round(max(vals), 1)

    # 4. Current memory usage per host
    mem_now = {}
    for r in prom_query('100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))'):
        if "error" in r:
            break
        inst = r.get("metric", {}).get("instance", "?")
        try:
            mem_now[inst] = round(float(r.get("value", [None, "0"])[1]), 1)
        except Exception:
            pass

    # 5. Disk usage >60% (root filesystem)
    disk_now = {}
    for r in prom_query('100 - (node_filesystem_avail_bytes{mountpoint="/",fstype!="tmpfs"} / node_filesystem_size_bytes{mountpoint="/",fstype!="tmpfs"} * 100)'):
        if "error" in r:
            break
        inst = r.get("metric", {}).get("instance", "?")
        try:
            val = round(float(r.get("value", [None, "0"])[1]), 1)
            if val > 60:
                disk_now[inst] = val
        except Exception:
            pass

    # 6. Current temperatures (all nodes with coretemp/Pi thermalzone)
    temps = {}
    for r in prom_query('node_hwmon_temp_celsius{sensor=~"temp0|temp1",chip=~"platform_coretemp_0|thermal_thermal_zone0"}'):
        if "error" in r:
            break
        inst = r.get("metric", {}).get("instance", "?")
        try:
            val = round(float(r.get("value", [None, "0"])[1]), 1)
            if inst not in temps or val > temps[inst]:
                temps[inst] = val
        except Exception:
            pass

    # 7. PBS backup status
    pbs_ok, pbs_failed = get_pbs_status()
    pbs_stale = get_pbs_ages()

    # 8. Energy & UPS
    energy = get_energy()

    # 9. Recent reboots
    reboots = get_recent_reboots(hours=24)

    # 10. Loki errors
    loki_errors = get_loki_errors(hours=24)

    return {
        "collected_at": now,
        "targets": {"up_count": len(up), "down": down},
        "alerts": {"critical": critical, "warnings": warnings},
        "performance": {
            "cpu_max_24h": dict(sorted(cpu_max.items(), key=lambda x: -x[1])[:15]),
            "memory_now":  dict(sorted(mem_now.items(),  key=lambda x: -x[1])[:15]),
            "disk_above_60pct": disk_now,
            "temperatures": dict(sorted(temps.items(), key=lambda x: -x[1])),
        },
        "backups": {
            "pbs_ok":    pbs_ok or [],
            "pbs_failed": pbs_failed or [],
            "pbs_stale": pbs_stale,
        },
        "energy": energy,
        "reboots_24h": reboots,
        "loki_errors": loki_errors,
    }


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
    up   = payload["targets"]["up_count"]
    down = payload["targets"]["down"]
    crit = payload["alerts"]["critical"]
    warn = payload["alerts"]["warnings"]
    perf = payload["performance"]
    back = payload["backups"]
    nrg  = payload["energy"]
    reboots = payload["reboots_24h"]
    logs = payload["loki_errors"]

    # ── Bericht 1: Status & Alerts ─────────────────────────────────────────
    alert_lines = []
    for a in crit:
        alert_lines.append(f"  [CRIT] {a['alertname']} — {a['instance']}")
    for a in warn:
        alert_lines.append(f"  [warn] {a['alertname']} — {a['instance']}")
    down_lines = [f"  DOWN: {d['instance']}" for d in down]
    reboot_lines = [f"  {r}" for r in reboots]

    msg1 = (
        f"=== HOSTING LOCAL — {ts} ===\n"
        f"Hosts: {up} UP"
        + (f", {len(down)} DOWN" if down else "")
        + f"\nAlerts: {len(crit)} critical, {len(warn)} warnings\n"
    )
    if down:
        msg1 += "\nDOWN:\n" + "\n".join(down_lines)
    if crit:
        msg1 += "\nCRITICAL:\n" + "\n".join(alert_lines[:8])
    elif warn:
        msg1 += "\nWarnings:\n" + "\n".join(alert_lines[:10])
    else:
        msg1 += "\nGeen actieve alerts ✓"
    if reboots:
        msg1 += "\n\nReboots (24h):\n" + "\n".join(reboot_lines)

    prio1 = "high" if crit or down else "default"
    tag1 = "rotating_light" if crit or down else "white_check_mark"
    s1 = ntfy_post("hl-morning-data", f"HL Status ({len(crit)}c/{len(warn)}w | {up}UP)", msg1,
                   tags=tag1, priority=prio1)

    # ── Bericht 2: Performance ─────────────────────────────────────────────
    cpu  = list(perf["cpu_max_24h"].items())[:10]
    mem  = [(k, v) for k, v in perf["memory_now"].items() if v > 70][:8]
    disk = list(perf["disk_above_60pct"].items())
    all_temps = list(perf["temperatures"].items())

    perf_lines = []
    if cpu:
        perf_lines.append("CPU piek 24h (top):")
        perf_lines += [f"  {k}: {v}%" for k, v in cpu]
    if mem:
        perf_lines.append("\nMemory >70% nu:")
        perf_lines += [f"  {k}: {v}%" for k, v in mem]
    if disk:
        perf_lines.append("\nDisk >60%:")
        perf_lines += [f"  {k}: {v}%" for k, v in disk]
    if all_temps:
        perf_lines.append("\nTemperaturen:")
        for k, v in all_temps:
            flag = " ⚠️" if v > 80 else (" 🔥" if v > 90 else "")
            perf_lines.append(f"  {k}: {v}°C{flag}")

    msg2 = "\n".join(perf_lines) if perf_lines else "Geen performance-issues"
    s2 = ntfy_post("hl-morning-data", "HL Performance", msg2)

    # ── Bericht 3: Backups & Energie ──────────────────────────────────────
    back_lines = []
    pbs_total = len(back["pbs_ok"]) + len(back["pbs_failed"])
    if pbs_total > 0:
        back_lines.append(f"PBS Backups: {len(back['pbs_ok'])}/{pbs_total} OK")
        if back["pbs_failed"]:
            back_lines.append("  FAILED: " + ", ".join(back["pbs_failed"]))
        if back["pbs_stale"]:
            back_lines.append("  VEROUDERD (>26u): " + ", ".join(back["pbs_stale"]))
        else:
            back_lines.append("  Alle recente backups tijdig ✓")
    else:
        back_lines.append("PBS: geen data")

    back_lines.append("")
    if "ups_w" in nrg:
        ups_str = f"UPS belasting: {nrg['ups_w']}W"
        if "ups_load_pct" in nrg:
            ups_str += f" ({nrg['ups_load_pct']}% load)"
        if "ups_battery_pct" in nrg:
            ups_str += f" | Batterij: {nrg['ups_battery_pct']}%"
        if "ups_runtime_min" in nrg:
            ups_str += f" ({nrg['ups_runtime_min']:.0f} min runtime)"
        back_lines.append(ups_str)
    if "solar_w" in nrg:
        back_lines.append(f"Zonnepanelen: {nrg['solar_w']}W huidig")
    if "solar_kwh_total" in nrg:
        back_lines.append(f"  Totaal opgewekt: {nrg['solar_kwh_total']} kWh")
    if "homelab_kwh_total" in nrg:
        back_lines.append(f"  Homelab verbruik: {nrg['homelab_kwh_total']} kWh totaal")

    pbs_bad = bool(back["pbs_failed"] or back["pbs_stale"])
    msg3 = "\n".join(back_lines)
    s3 = ntfy_post("hl-morning-data", "HL Backups & Energie",
                   msg3, tags="floppy_disk", priority="high" if pbs_bad else "default")

    # ── Bericht 4: Log errors ──────────────────────────────────────────────
    if logs and "error" not in logs[0]:
        seen = {}
        for entry in logs:
            h = entry.get("host", "?")
            if h not in seen:
                seen[h] = []
            line = entry.get("line", "")
            # dedup: skip als bijna identiek aan vorige
            if not any(line[:60] in prev for prev in seen[h]):
                if len(seen[h]) < 3:
                    seen[h].append(line)
        loki_lines = []
        for host, lines in list(seen.items())[:10]:
            loki_lines.append(f"[{host}]")
            loki_lines += [f"  {l[:120]}" for l in lines]
        msg4 = "\n".join(loki_lines) if loki_lines else "Geen unieke log-errors"
        err_count = len(logs)
    else:
        msg4 = "Loki niet bereikbaar of geen errors"
        err_count = 0

    s4 = ntfy_post("hl-morning-data", f"HL Logs ({err_count} errors)", msg4)

    return s1, s2, s3, s4


if __name__ == "__main__":
    payload = collect()

    down_count  = len(payload["targets"]["down"])
    crit_count  = len(payload["alerts"]["critical"])
    warn_count  = len(payload["alerts"]["warnings"])
    loki_count  = len(payload["loki_errors"])
    pbs_ok      = len(payload["backups"]["pbs_ok"])
    pbs_fail    = len(payload["backups"]["pbs_failed"])

    print(f"Collected: {payload['targets']['up_count']} up, {down_count} down, "
          f"{crit_count} critical, {warn_count} warnings, {loki_count} log errors, "
          f"PBS {pbs_ok}ok/{pbs_fail}fail")

    statuses = push_to_ntfy(payload)
    labels = ("alerts", "perf", "backups", "logs")
    print("ntfy push: " + ", ".join(f"{l}={s}" for l, s in zip(labels, statuses)))
    sys.exit(0 if all(s == 200 for s in statuses) else 1)
