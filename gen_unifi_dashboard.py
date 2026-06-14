#!/usr/bin/env python3
"""
Genereert unifi-poller-kiosk.json — UniFi Poller dashboard.

Metrics komen van ghcr.io/unpoller/unpoller (v2) met namespace 'unifi'.
Actief zodra UNIFI_POLLER_USER/PASS ingevuld zijn in .env op METRICSSERVER.

Layout:
  Sectie 1: Overzicht (clients, WAN snelheid)
  Sectie 2: Access Points (status, clients, radio kwaliteit)
  Sectie 3: Wireless tijdreeks (traffic + channel utilization)
  Sectie 4: Switches PoE (totaal vermogen + per poort)
"""
import json, os

OUT = os.path.join(os.path.dirname(__file__),
                   "grafana/provisioning/dashboards/unifi-poller.json")

# ── helpers ──────────────────────────────────────────────────────────────────

def text_panel(pid, title, x, y, w, h):
    return {
        "id": pid, "type": "text", "transparent": True,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "options": {"mode": "markdown", "content": f"## {title}"},
    }

def stat(pid, title, expr, unit="short", x=0, y=0, w=6, h=4,
         mappings=None, thresholds=None, color="green"):
    p = {
        "id": pid, "type": "stat",
        "title": title,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [{"expr": expr, "legendFormat": "", "refId": "A"}],
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "orientation": "auto",
            "textMode": "auto",
            "colorMode": "background",
            "graphMode": "none",
            "justifyMode": "center",
            "text": {"valueSize": 40, "titleSize": 14},
        },
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "color": {"mode": "fixed", "fixedColor": color},
                "thresholds": thresholds or {
                    "mode": "absolute",
                    "steps": [{"color": "green", "value": None}],
                },
                "mappings": mappings or [],
            },
            "overrides": [],
        },
    }
    return p

def timeseries(pid, title, targets, unit="Bps", x=0, y=0, w=24, h=8,
               stacking=False, legend_right=False):
    return {
        "id": pid, "type": "timeseries",
        "title": title,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": targets,
        "options": {
            "tooltip": {"mode": "multi", "sort": "desc"},
            "legend": {
                "showLegend": True,
                "displayMode": "table",
                "placement": "right" if legend_right else "bottom",
                "calcs": ["lastNotNull", "max"],
            },
        },
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "custom": {
                    "lineWidth": 1,
                    "fillOpacity": 10,
                    "stacking": {"mode": "normal" if stacking else "none"},
                    "showPoints": "never",
                },
            },
            "overrides": [],
        },
    }

def table_panel(pid, title, targets, x=0, y=0, w=24, h=8):
    return {
        "id": pid, "type": "table",
        "title": title,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": targets,
        "options": {
            "sortBy": [{"displayName": "Name", "desc": False}],
            "footer": {"show": False},
        },
        "fieldConfig": {
            "defaults": {"custom": {"align": "auto", "displayMode": "auto"}},
            "overrides": [],
        },
        "transformations": [
            {"id": "merge", "options": {}},
            {"id": "organize", "options": {
                "excludeByName": {"Time": True, "__name__": True,
                                  "job": True, "instance": True},
                "renameByName": {
                    "name": "AP", "model": "Model", "ip": "IP",
                    "mac": "MAC", "version": "Firmware", "state": "Status",
                },
            }},
        ],
    }


# ── panelen opbouwen ──────────────────────────────────────────────────────────

panels = []
pid = 1

# ─────────────────────────────────────────────────────────────────────────────
# Sectie 1: Netwerk Overzicht (y=0..9)
# ─────────────────────────────────────────────────────────────────────────────
panels.append(text_panel(pid, "Netwerk Overzicht", 0, 0, 24, 2)); pid += 1

# Totaal verbonden clients (site-level)
panels.append(stat(
    pid, "Verbonden clients",
    'sum(unifi_site_num_sta)',
    unit="short", x=0, y=2, w=4, h=5, color="blue",
)); pid += 1

# Clients per radio (2.4GHz vs 5GHz vs 6GHz)
panels.append(stat(
    pid, "Clients 2.4 GHz",
    'sum(unifi_uap_num_sta{radio="ng"})',
    unit="short", x=4, y=2, w=4, h=5, color="#5794F2",
)); pid += 1

panels.append(stat(
    pid, "Clients 5 GHz",
    'sum(unifi_uap_num_sta{radio="na"})',
    unit="short", x=8, y=2, w=4, h=5, color="#56A64B",
)); pid += 1

panels.append(stat(
    pid, "Clients 6 GHz",
    'sum(unifi_uap_num_sta{radio="6e"})',
    unit="short", x=12, y=2, w=4, h=5, color="#37872D",
)); pid += 1

# WAN throughput
panels.append(stat(
    pid, "WAN Download",
    'sum(rate(unifi_site_wan_rx_bytes_total[5m])) * 8',
    unit="bps", x=16, y=2, w=4, h=5, color="#F2495C",
    thresholds={
        "mode": "absolute",
        "steps": [
            {"color": "green", "value": None},
            {"color": "yellow", "value": 500000000},
            {"color": "red", "value": 900000000},
        ],
    },
)); pid += 1

panels.append(stat(
    pid, "WAN Upload",
    'sum(rate(unifi_site_wan_tx_bytes_total[5m])) * 8',
    unit="bps", x=20, y=2, w=4, h=5, color="#FF780A",
    thresholds={
        "mode": "absolute",
        "steps": [
            {"color": "green", "value": None},
            {"color": "yellow", "value": 200000000},
            {"color": "red", "value": 450000000},
        ],
    },
)); pid += 1

# ─────────────────────────────────────────────────────────────────────────────
# Sectie 2: Access Points (y=7..20)
# ─────────────────────────────────────────────────────────────────────────────
panels.append(text_panel(pid, "Access Points", 0, 7, 24, 2)); pid += 1

# AP Status tabel (via unifi_uap_info)
panels.append(table_panel(
    pid, "AP Status",
    targets=[
        {
            "expr": 'unifi_uap_info',
            "legendFormat": "{{name}}",
            "refId": "A",
            "instant": True,
        }
    ],
    x=0, y=9, w=14, h=7,
)); pid += 1

# Clients per AP (stat per AP)
panels.append(timeseries(
    pid, "Clients per AP",
    targets=[
        {
            "expr": 'sum by (name) (unifi_uap_num_sta)',
            "legendFormat": "{{name}}",
            "refId": "A",
        }
    ],
    unit="short", x=14, y=9, w=10, h=7,
)); pid += 1

# AP Uptime
panels.append(timeseries(
    pid, "AP Uptime",
    targets=[
        {
            "expr": 'unifi_uap_uptime_seconds',
            "legendFormat": "{{name}}",
            "refId": "A",
        }
    ],
    unit="s", x=0, y=16, w=12, h=6,
)); pid += 1

# Satisfaction score per AP (0-100)
panels.append(timeseries(
    pid, "Wireless Satisfaction (%)",
    targets=[
        {
            "expr": 'avg by (name, radio) (unifi_uap_radio_satisfaction_ratio * 100)',
            "legendFormat": "{{name}} {{radio}}",
            "refId": "A",
        }
    ],
    unit="percent", x=12, y=16, w=12, h=6,
)); pid += 1

# ─────────────────────────────────────────────────────────────────────────────
# Sectie 3: Wireless Traffic tijdreeks (y=22..38)
# ─────────────────────────────────────────────────────────────────────────────
panels.append(text_panel(pid, "Wireless Traffic", 0, 22, 24, 2)); pid += 1

# AP Radio RX/TX traffic
panels.append(timeseries(
    pid, "AP Radio Traffic — Download (RX)",
    targets=[
        {
            "expr": 'sum by (name, radio) (rate(unifi_uap_radio_rx_bytes_total[5m])) * 8',
            "legendFormat": "{{name}} {{radio}} ↓",
            "refId": "A",
        }
    ],
    unit="bps", x=0, y=24, w=12, h=8, legend_right=True,
)); pid += 1

panels.append(timeseries(
    pid, "AP Radio Traffic — Upload (TX)",
    targets=[
        {
            "expr": 'sum by (name, radio) (rate(unifi_uap_radio_tx_bytes_total[5m])) * 8',
            "legendFormat": "{{name}} {{radio}} ↑",
            "refId": "A",
        }
    ],
    unit="bps", x=12, y=24, w=12, h=8, legend_right=True,
)); pid += 1

# Channel Utilization
panels.append(timeseries(
    pid, "Channel Utilization — Self (%)",
    targets=[
        {
            "expr": 'avg by (name, radio) (unifi_uap_radio_cu_self_ratio * 100)',
            "legendFormat": "{{name}} {{radio}}",
            "refId": "A",
        }
    ],
    unit="percent", x=0, y=32, w=12, h=6,
)); pid += 1

panels.append(timeseries(
    pid, "TX Power (dBm)",
    targets=[
        {
            "expr": 'unifi_uap_radio_tx_power_dbm',
            "legendFormat": "{{name}} {{radio}}",
            "refId": "A",
        }
    ],
    unit="dBm", x=12, y=32, w=12, h=6,
)); pid += 1

# ─────────────────────────────────────────────────────────────────────────────
# Sectie 4: Switches PoE (y=38..54)
# ─────────────────────────────────────────────────────────────────────────────
panels.append(text_panel(pid, "Switches — PoE & Port Traffic", 0, 38, 24, 2)); pid += 1

# Totaal PoE vermogen per switch
panels.append(stat(
    pid, "Totaal PoE Vermogen",
    'sum(unifi_usw_port_poe_watts)',
    unit="watt", x=0, y=40, w=6, h=4, color="#FF780A",
    thresholds={
        "mode": "absolute",
        "steps": [
            {"color": "green", "value": None},
            {"color": "yellow", "value": 100},
            {"color": "red", "value": 180},
        ],
    },
)); pid += 1

# PoE per poort (tijdreeks)
panels.append(timeseries(
    pid, "PoE Vermogen per Poort (W)",
    targets=[
        {
            "expr": 'unifi_usw_port_poe_watts > 0',
            "legendFormat": "{{name}} port {{port_name}}",
            "refId": "A",
        }
    ],
    unit="watt", x=6, y=40, w=18, h=8,
)); pid += 1

# Switch port traffic RX
panels.append(timeseries(
    pid, "Switch Port Traffic — Download (RX)",
    targets=[
        {
            "expr": 'sum by (name, port_name) (rate(unifi_usw_port_rx_bytes_total[5m])) * 8 > 1000',
            "legendFormat": "{{name}} p{{port_name}} ↓",
            "refId": "A",
        }
    ],
    unit="bps", x=0, y=48, w=12, h=6, legend_right=True,
)); pid += 1

# Switch port traffic TX
panels.append(timeseries(
    pid, "Switch Port Traffic — Upload (TX)",
    targets=[
        {
            "expr": 'sum by (name, port_name) (rate(unifi_usw_port_tx_bytes_total[5m])) * 8 > 1000',
            "legendFormat": "{{name}} p{{port_name}} ↑",
            "refId": "A",
        }
    ],
    unit="bps", x=12, y=48, w=12, h=6, legend_right=True,
)); pid += 1

# ─────────────────────────────────────────────────────────────────────────────
# Dashboard definitie
# ─────────────────────────────────────────────────────────────────────────────

dashboard = {
    "uid": "unifi-poller-hl",
    "title": "UniFi Poller — APs & Switches",
    "tags": ["unifi", "network", "hostinglocal"],
    "timezone": "browser",
    "schemaVersion": 38,
    "version": 1,
    "refresh": "1m",
    "time": {"from": "now-3h", "to": "now"},
    "panels": panels,
    "templating": {"list": []},
    "annotations": {"list": []},
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(dashboard, f, indent=2, ensure_ascii=False)

print(f"Geschreven: {OUT}")
print(f"Panels: {len(panels)}")
for p in panels:
    gt = p.get('gridPos', {})
    print(f"  [{p['type']:12s}] y={gt.get('y'):2d} h={gt.get('h'):2d}  {p.get('title','(geen titel)')}")
