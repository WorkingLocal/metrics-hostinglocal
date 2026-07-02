#!/usr/bin/env python3
"""Generate all 4 kiosk dashboard JSONs with:
- Reverted text sizes (titleSize halved)
- Row panels → text panels (h=2) for bigger section titles
- CPU+rack timeseries added to dashboard 1
- Dashboard 4: PBS + rclone backups + NTFY placeholder
"""
import json, os

DASH = r"c:\Users\Lenovo\Github\metrics-hostinglocal\grafana\provisioning\dashboards"
DS   = r"c:\Users\Lenovo\Github\metrics-hostinglocal\grafana\provisioning\datasources"

def W(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"OK: {os.path.basename(path)}")

def header(pid, title, y):
    return {
        "id": pid, "type": "text", "title": "", "transparent": True,
        "gridPos": {"h": 2, "w": 24, "x": 0, "y": y},
        "options": {
            "content": f"## {title}", "mode": "markdown",
            "code": {"language": "plaintext", "showLineNumbers": False, "showMiniMap": False}
        },
        "fieldConfig": {"defaults": {}, "overrides": []}
    }

# ── TEMPERATURES ──────────────────────────────
def cpu_stat(pid, title, desc, x, y, expr, leg, thresh_steps=None):
    if thresh_steps is None:
        thresh_steps = [
            {"color":"green","value":None},{"color":"yellow","value":60},
            {"color":"orange","value":75},{"color":"red","value":85}
        ]
    return {
        "id": pid, "type": "stat", "title": title, "description": desc,
        "gridPos": {"h": 5, "w": 4, "x": x, "y": y},
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"]},
            "colorMode": "background", "graphMode": "area",
            "textMode": "value_and_name", "justifyMode": "center",
            "text": {"valueSize": 52, "titleSize": 18}
        },
        "fieldConfig": {
            "defaults": {
                "unit": "celsius",
                "thresholds": {"mode": "absolute", "steps": thresh_steps}
            }, "overrides": []
        },
        "targets": [{"expr": expr, "legendFormat": leg, "refId": "A"}]
    }

def rack_stat(pid, title, desc, x, y, expr, leg):
    return {
        "id": pid, "type": "stat", "title": title, "description": desc,
        "gridPos": {"h": 7, "w": 6, "x": x, "y": y},
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"]},
            "colorMode": "background", "graphMode": "area",
            "textMode": "value_and_name", "justifyMode": "center",
            "text": {"valueSize": 52, "titleSize": 18}
        },
        "fieldConfig": {
            "defaults": {
                "unit": "celsius",
                "thresholds": {"mode": "absolute", "steps": [
                    {"color":"green","value":None},{"color":"yellow","value":30},
                    {"color":"orange","value":38},{"color":"red","value":45}
                ]}
            }, "overrides": []
        },
        "targets": [{"expr": expr, "legendFormat": leg, "refId": "A"}]
    }

pi_thresh = [
    {"color":"green","value":None},{"color":"yellow","value":60},
    {"color":"orange","value":70},{"color":"red","value":80}
]

temps = {
    "title": "Serverrack Kiosk — Temperaturen",
    "uid": "serverrack-kiosk",
    "description": "FHD kiosk scherm 1 — CPU + Rack temperaturen + tijdreeks",
    "timezone": "browser", "refresh": "30s", "schemaVersion": 38, "version": 7,
    "time": {"from": "now-2h", "to": "now"},
    "tags": ["kiosk", "temperatures"],
    "panels": [
        header(1, "CPU Temperaturen", 0),
        cpu_stat(2,"PVE-MS01-I9","Intel i9 MS-01 — Package °C",0,2,
            'max by (instance) (node_hwmon_temp_celsius{instance="PVE-MS01-I9", chip=~".*coretemp.*", sensor="temp1"})','AI-NODE-I9'),
        cpu_stat(3,"PVE-MS01-I5","Intel i5 MS-01 — Package °C",4,2,
            'max by (instance) (node_hwmon_temp_celsius{instance="PVE-MS01-I5", chip=~".*coretemp.*", sensor="temp1"})','AI-NODE-I5'),
        cpu_stat(4,"NETWORKSERVER","Proxmox i3-N305 — Package °C",8,2,
            'max by (instance) (node_hwmon_temp_celsius{instance="NETWORKSERVER", chip=~".*coretemp.*", sensor="temp1"})','NETWORKSERVER'),
        cpu_stat(5,"MEDIASERVER","Proxmox NUC i5-8259U — Package °C",12,2,
            'max by (instance) (node_hwmon_temp_celsius{instance="MEDIASERVER", chip=~".*coretemp.*", sensor="temp1"})','MEDIASERVER'),
        cpu_stat(6,"METRICSSERVER","Dell OptiPlex i5-7500 — Package °C",16,2,
            'max by (instance) (node_hwmon_temp_celsius{instance="METRICSSERVER", chip=~".*coretemp.*", sensor="temp1"})','METRICSSERVER'),
        cpu_stat(7,"HAOS NUC","Intel NUC i3 — CPU via System Monitor °C",20,2,
            'homeassistant_sensor_temperature_celsius{entity="sensor.system_monitor_processortemperatuur", job="smarthomeserver"}','HAOS NUC'),
        cpu_stat(8,"WINDOWSSERVER2025","Dual Xeon Silver 4114 — max Package °C",0,7,
            'max(windows_hardware_temperature_celsius{instance="WINDOWSSERVER2025", sensor="CPU_Package"})','WINSVR2025'),
        cpu_stat(9,"NUT-SERVER Pi","Raspberry Pi 3B — zone temp °C",4,7,
            'node_hwmon_temp_celsius{instance="NUT-SERVER", chip="thermal_thermal_zone0", sensor="temp0"}','NUT-SERVER Pi',pi_thresh),
        cpu_stat(10,"FANSERVER Pi4","Raspberry Pi 4 — zone temp °C",8,7,
            'node_hwmon_temp_celsius{instance="FANSERVER", chip="thermal_thermal_zone0", sensor="temp0"}','FANSERVER Pi4',pi_thresh),
        cpu_stat(11,"PROXMOXMANAGER","NUC Celeron — Package °C",12,7,
            'max by (instance) (node_hwmon_temp_celsius{instance="PROXMOXMANAGER", chip=~".*coretemp.*", sensor="temp1"})','PROXMOXMANAGER'),
        cpu_stat(12,"TRAVELSERVER","Minisforum S100 TrueNAS — Package °C",16,7,
            'max by (instance) (node_hwmon_temp_celsius{instance="TRAVELSERVER", chip=~".*coretemp.*", sensor="temp1"})','TRAVELSERVER'),
        cpu_stat(13,"FILESERVER","Synology DS423+ Celeron J4125 — CPU °C",20,7,
            'max by (instance) (node_hwmon_temp_celsius{instance="FILESERVER", chip=~".*coretemp.*"})','FILESERVER'),
        header(14, "Rack Temperaturen", 12),
        {
            "id": 15, "type": "stat",
            "title": "Rack — Ambient", "description": "TP357 op de kast — luchttemperatuur berging",
            "gridPos": {"h": 7, "w": 6, "x": 0, "y": 14},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]},
                "colorMode": "background", "graphMode": "area",
                "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 52, "titleSize": 18}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "celsius",
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"blue","value":None},{"color":"green","value":18},
                        {"color":"yellow","value":30},{"color":"orange","value":38},{"color":"red","value":45}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": 'homeassistant_sensor_temperature_celsius{entity="sensor.tp357_e33d_temperature", job="smarthomeserver"}',
                         "legendFormat": "Rack Ambient", "refId": "A"}]
        },
        rack_stat(40,"Rack — Networkserver","TP357 bij passieve networkserver — schap temp",6,14,
            'homeassistant_sensor_temperature_celsius{entity="sensor.tp357_c5a9_temperature", job="smarthomeserver"}','Rack Networkserver'),
        rack_stat(41,"Rack — Mediaserver","TP357 tussen NUCs — mediaserver zone temp",12,14,
            'homeassistant_sensor_temperature_celsius{entity="sensor.tp357_9f54_temperature", job="smarthomeserver"}','Rack Mediaserver'),
        rack_stat(42,"Rack — AI-nodes","TP357 tussen MS-01's — AI-nodes zone temp",18,14,
            'homeassistant_sensor_temperature_celsius{entity="sensor.tp357_5eb7_temperature", job="smarthomeserver"}','Rack AI-nodes'),
        header(49, "CPU & Rack Tijdreeks (2u)", 21),
        {
            "id": 50, "type": "timeseries",
            "title": "CPU & Rack Temperaturen — 2 uur",
            "gridPos": {"h": 13, "w": 24, "x": 0, "y": 23},
            "options": {
                "tooltip": {"mode": "multi", "sort": "desc"},
                "legend": {"displayMode": "table", "placement": "right", "calcs": ["lastNotNull", "max"]}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "celsius",
                    "custom": {"lineWidth": 2, "fillOpacity": 10},
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"green","value":None},{"color":"yellow","value":60},{"color":"red","value":80}
                    ]}
                }, "overrides": []
            },
            "targets": [
                {"expr": 'max by (instance) (node_hwmon_temp_celsius{instance=~"PVE-MS01-I9|PVE-MS01-I5|NETWORKSERVER|MEDIASERVER|METRICSSERVER|PROXMOXMANAGER|TRAVELSERVER|FILESERVER", chip=~".*coretemp.*", sensor="temp1"})',
                 "legendFormat": "{{instance}} CPU", "refId": "A"},
                {"expr": 'node_hwmon_temp_celsius{instance=~"NUT-SERVER|FANSERVER", chip="thermal_thermal_zone0", sensor="temp0"}',
                 "legendFormat": "{{instance}} CPU", "refId": "B"},
                {"expr": 'homeassistant_sensor_temperature_celsius{entity="sensor.system_monitor_processortemperatuur", job="smarthomeserver"}',
                 "legendFormat": "HAOS NUC CPU", "refId": "C"},
                {"expr": 'max(windows_hardware_temperature_celsius{instance="WINDOWSSERVER2025", sensor="CPU_Package"})',
                 "legendFormat": "WINSVR2025 CPU", "refId": "D"},
                {"expr": 'homeassistant_sensor_temperature_celsius{entity=~"sensor.tp357_(e33d|c5a9|9f54|5eb7)_temperature", job="smarthomeserver"}',
                 "legendFormat": "Rack {{entity}}", "refId": "E"}
            ]
        }
    ]
}
W(os.path.join(DASH, "temperatures-kiosk.json"), temps)

# ── DISKS ─────────────────────────────────────
def nvme_stat(pid, title, x, expr, leg):
    return {
        "id": pid, "type": "stat", "title": title, "description": "Composite sensor temp1",
        "gridPos": {"h": 5, "w": 6, "x": x, "y": 2},
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"]},
            "colorMode": "background", "graphMode": "area",
            "textMode": "value_and_name", "justifyMode": "center",
            "text": {"valueSize": 64, "titleSize": 22}
        },
        "fieldConfig": {
            "defaults": {
                "unit": "celsius",
                "thresholds": {"mode": "absolute", "steps": [
                    {"color":"green","value":None},{"color":"yellow","value":55},
                    {"color":"orange","value":70},{"color":"red","value":80}
                ]}
            }, "overrides": []
        },
        "targets": [{"expr": expr, "legendFormat": leg, "refId": "A"}]
    }

disks = {
    "title": "Serverrack Kiosk — NVMe & Schijven",
    "uid": "serverrack-disks",
    "description": "FHD kiosk scherm 2 — NVMe temperaturen, FILESERVER schijven, tijdreeks",
    "timezone": "browser", "refresh": "30s", "schemaVersion": 38, "version": 2,
    "time": {"from": "now-6h", "to": "now"},
    "tags": ["kiosk", "disks"],
    "panels": [
        header(1, "NVMe Temperaturen", 0),
        nvme_stat(2,"AI-I9 — NVMe",0,'max by (instance) (node_hwmon_temp_celsius{instance="PVE-MS01-I9", chip=~"nvme.*", sensor="temp1"})','AI-I9 NVMe'),
        nvme_stat(3,"AI-I5 — NVMe",6,'max by (instance) (node_hwmon_temp_celsius{instance="PVE-MS01-I5", chip=~"nvme.*", sensor="temp1"})','AI-I5 NVMe'),
        nvme_stat(4,"NETWORK — NVMe",12,'max by (instance) (node_hwmon_temp_celsius{instance="NETWORKSERVER", chip=~"nvme.*", sensor="temp1"})','NETWORK NVMe'),
        nvme_stat(5,"MEDIA — NVMe",18,'max by (instance) (node_hwmon_temp_celsius{instance="MEDIASERVER", chip=~"nvme.*", sensor="temp1"})','MEDIA NVMe'),
        header(6, "FILESERVER Schijven", 7),
        {
            "id": 7, "type": "stat",
            "title": "FILESERVER — Disks max",
            "description": "DS423+ — hoogste schijftemperatuur (4x HDD + 2x M.2)",
            "gridPos": {"h": 4, "w": 8, "x": 0, "y": 9},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]},
                "colorMode": "background", "graphMode": "area",
                "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 56, "titleSize": 18}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "celsius",
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"green","value":None},{"color":"yellow","value":40},
                        {"color":"orange","value":50},{"color":"red","value":58}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": 'max(homeassistant_sensor_temperature_celsius{entity=~"sensor.fileserver_(m_2_)?drive_[0-9]_temperatuur", job="smarthomeserver"})',
                         "legendFormat": "FILE max", "refId": "A"}]
        },
        {
            "id": 8, "type": "stat",
            "title": "FILESERVER — Alle schijven",
            "description": "DS423+ — individuele schijftemperaturen",
            "gridPos": {"h": 4, "w": 16, "x": 8, "y": 9},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]},
                "colorMode": "background", "graphMode": "none",
                "textMode": "value_and_name", "justifyMode": "auto",
                "text": {"valueSize": 28, "titleSize": 12}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "celsius",
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"green","value":None},{"color":"yellow","value":40},
                        {"color":"orange","value":50},{"color":"red","value":58}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": 'homeassistant_sensor_temperature_celsius{entity=~"sensor.fileserver_(m_2_)?drive_[0-9]_temperatuur", job="smarthomeserver"}',
                         "legendFormat": "{{entity}}", "refId": "A"}]
        },
        header(9, "Tijdreeks — NVMe & Disks (6u)", 13),
        {
            "id": 10, "type": "timeseries",
            "title": "NVMe & Schijf Temperaturen",
            "gridPos": {"h": 7, "w": 24, "x": 0, "y": 15},
            "options": {
                "tooltip": {"mode": "multi", "sort": "desc"},
                "legend": {"displayMode": "table", "placement": "right", "calcs": ["lastNotNull", "max"]}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "celsius",
                    "custom": {"lineWidth": 2, "fillOpacity": 10},
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"green","value":None},{"color":"yellow","value":55},{"color":"red","value":80}
                    ]}
                }, "overrides": []
            },
            "targets": [
                {"expr": 'max by (instance) (node_hwmon_temp_celsius{instance=~"PVE-MS01-I9|PVE-MS01-I5|NETWORKSERVER|MEDIASERVER", chip=~"nvme.*", sensor="temp1"})',
                 "legendFormat": "{{instance}} NVMe", "refId": "A"},
                {"expr": 'homeassistant_sensor_temperature_celsius{entity=~"sensor.fileserver_(m_2_)?drive_[0-9]_temperatuur", job="smarthomeserver"}',
                 "legendFormat": "FILE {{entity}}", "refId": "B"}
            ]
        }
    ]
}
W(os.path.join(DASH, "disks-kiosk.json"), disks)

# ── ENERGIE ───────────────────────────────────
energie = {
    "title": "Serverrack Kiosk — Energie",
    "uid": "serverrack-energie",
    "description": "FHD kiosk scherm 3 — BEEM zonnepanelen, EATON UPS verbruik, 7-dagen vergelijking",
    "timezone": "browser", "refresh": "30s", "schemaVersion": 38, "version": 2,
    "time": {"from": "now-7d", "to": "now"},
    "tags": ["kiosk", "energie"],
    "panels": [
        header(1, "Zonnepanelen (BEEM)", 0),
        {
            "id": 2, "type": "stat", "title": "Huidig Vermogen",
            "description": "BEEM plug-in zonnepanelen — actuele output",
            "gridPos": {"h": 4, "w": 8, "x": 0, "y": 2},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                "graphMode": "area", "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 60, "titleSize": 20}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "watt",
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"blue","value":None},{"color":"green","value":10},
                        {"color":"yellow","value":150},{"color":"orange","value":300}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": 'homeassistant_sensor_power_w{entity="sensor.beem_energy_thomas_vandromme_current_power", job="smarthomeserver"}',
                         "legendFormat": "Zonnepanelen", "refId": "A"}]
        },
        {
            "id": 3, "type": "stat", "title": "Vandaag",
            "description": "BEEM — opgewekte energie vandaag",
            "gridPos": {"h": 4, "w": 8, "x": 8, "y": 2},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                "graphMode": "none", "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 60, "titleSize": 20}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "watth",
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"blue","value":None},{"color":"green","value":100},{"color":"yellow","value":800}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": 'homeassistant_sensor_energy_wh{entity="sensor.beem_energy_thomas_vandromme_daily_energy", job="smarthomeserver"}',
                         "legendFormat": "Vandaag", "refId": "A"}]
        },
        {
            "id": 4, "type": "stat", "title": "Deze Maand",
            "description": "BEEM — opgewekte energie deze maand",
            "gridPos": {"h": 4, "w": 8, "x": 16, "y": 2},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                "graphMode": "none", "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 60, "titleSize": 20}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "kwatth", "decimals": 1,
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"blue","value":None},{"color":"green","value":1},{"color":"yellow","value":10}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": 'homeassistant_sensor_energy_wh{entity="sensor.beem_energy_thomas_vandromme_monthly_energy", job="smarthomeserver"} / 1000',
                         "legendFormat": "Deze Maand", "refId": "A"}]
        },
        header(5, "EATON UPS — Rack Verbruik", 6),
        {
            "id": 6, "type": "stat", "title": "Rack Verbruik",
            "description": "EATON EX 1000 — totaal vermogen rack",
            "gridPos": {"h": 4, "w": 6, "x": 0, "y": 8},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                "graphMode": "area", "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 56, "titleSize": 18}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "watt",
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"green","value":None},{"color":"yellow","value":400},
                        {"color":"orange","value":600},{"color":"red","value":800}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": 'homeassistant_sensor_power_w{entity="sensor.eatonups_current_real_power", job="smarthomeserver"}',
                         "legendFormat": "UPS Rack", "refId": "A"}]
        },
        {
            "id": 7, "type": "stat", "title": "UPS Belasting",
            "description": "EATON — belasting als % van 900W nominaal",
            "gridPos": {"h": 4, "w": 6, "x": 6, "y": 8},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                "graphMode": "area", "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 56, "titleSize": 18}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "percent",
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"green","value":None},{"color":"yellow","value":50},
                        {"color":"orange","value":75},{"color":"red","value":90}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": 'homeassistant_sensor_unit_percent{entity="sensor.eatonups_load", job="smarthomeserver"}',
                         "legendFormat": "UPS Load", "refId": "A"}]
        },
        {
            "id": 8, "type": "stat", "title": "Batterij",
            "description": "EATON — batterijcapaciteit",
            "gridPos": {"h": 4, "w": 6, "x": 12, "y": 8},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                "graphMode": "none", "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 56, "titleSize": 18}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "percent",
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"red","value":None},{"color":"orange","value":20},
                        {"color":"yellow","value":50},{"color":"green","value":80}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": 'homeassistant_sensor_battery_percent{entity="sensor.eatonups_battery_charge", job="smarthomeserver"}',
                         "legendFormat": "Batterij", "refId": "A"}]
        },
        {
            "id": 9, "type": "stat", "title": "Runtime",
            "description": "EATON — beschikbare batterijreserve",
            "gridPos": {"h": 4, "w": 6, "x": 18, "y": 8},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                "graphMode": "none", "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 56, "titleSize": 18}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "dtdurations",
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"red","value":None},{"color":"orange","value":300},
                        {"color":"yellow","value":600},{"color":"green","value":900}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": 'homeassistant_sensor_duration_s{entity="sensor.eatonups_battery_runtime", job="smarthomeserver"}',
                         "legendFormat": "Runtime", "refId": "A"}]
        },
        header(10, "Solar vs Rack — 7 dagen", 12),
        {
            "id": 11, "type": "timeseries",
            "title": "Zonnepanelen vs Rack Verbruik — 7 dagen",
            "description": "Groen = solar productie, Rood = UPS rack verbruik. Doel: solar ≥ rack.",
            "gridPos": {"h": 8, "w": 24, "x": 0, "y": 14},
            "options": {
                "tooltip": {"mode": "multi", "sort": "desc"},
                "legend": {"displayMode": "table", "placement": "right", "calcs": ["lastNotNull", "mean", "max"]}
            },
            "fieldConfig": {
                "defaults": {"unit": "watt", "custom": {"lineWidth": 2, "fillOpacity": 15}},
                "overrides": [
                    {"matcher": {"id": "byName", "options": "Zonnepanelen"},
                     "properties": [{"id": "color", "value": {"fixedColor": "#73BF69", "mode": "fixed"}}]},
                    {"matcher": {"id": "byName", "options": "UPS Rack"},
                     "properties": [{"id": "color", "value": {"fixedColor": "#F2495C", "mode": "fixed"}}]}
                ]
            },
            "targets": [
                {"expr": 'homeassistant_sensor_power_w{entity="sensor.beem_energy_thomas_vandromme_current_power", job="smarthomeserver"}',
                 "legendFormat": "Zonnepanelen", "refId": "A"},
                {"expr": 'homeassistant_sensor_power_w{entity="sensor.eatonups_current_real_power", job="smarthomeserver"}',
                 "legendFormat": "UPS Rack", "refId": "B"}
            ]
        }
    ]
}
W(os.path.join(DASH, "energie-kiosk.json"), energie)

# ── NOTIFICATIES / BACKUPS (dashboard 4) ──────
notify = {
    "title": "Serverrack Kiosk — Backups & Notificaties",
    "uid": "serverrack-notify",
    "description": "FHD kiosk scherm 4 — PBS backup status, rclone jobs, NTFY berichten, tijdreeks",
    "timezone": "browser", "refresh": "5m", "schemaVersion": 38, "version": 1,
    "time": {"from": "now-7d", "to": "now"},
    "tags": ["kiosk", "backups", "ntfy"],
    "panels": [
        header(1, "PBS Backup — Proxmox Backup Server", 0),
        {
            "id": 2, "type": "stat", "title": "PBS Opslag Gebruik",
            "description": "Proxmox Backup Server — gebruikte opslagruimte %",
            "gridPos": {"h": 5, "w": 6, "x": 0, "y": 2},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                "graphMode": "area", "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 52, "titleSize": 18}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "percent", "decimals": 1,
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"green","value":None},{"color":"yellow","value":60},
                        {"color":"orange","value":80},{"color":"red","value":90}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": "pbs_datastore_used_bytes / pbs_datastore_total_bytes * 100",
                         "legendFormat": "PBS Gebruik %", "refId": "A"}]
        },
        {
            "id": 3, "type": "stat", "title": "PBS Vrije Ruimte",
            "description": "Proxmox Backup Server — vrije opslagruimte",
            "gridPos": {"h": 5, "w": 6, "x": 6, "y": 2},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                "graphMode": "none", "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 52, "titleSize": 18}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "bytes",
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"red","value":None},
                        {"color":"orange","value":107374182400},
                        {"color":"yellow","value":536870912000},
                        {"color":"green","value":1099511627776}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": "pbs_datastore_available_bytes",
                         "legendFormat": "PBS Vrij", "refId": "A"}]
        },
        {
            "id": 4, "type": "stat", "title": "PBS Backup Status",
            "description": "Proxmox Backup Server — laatste backup taak (1=OK, 0=FAIL)",
            "gridPos": {"h": 5, "w": 6, "x": 12, "y": 2},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                "graphMode": "none", "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 52, "titleSize": 18},
                "mappings": [
                    {"type": "value", "options": {
                        "1": {"text": "OK", "color": "green", "index": 0},
                        "0": {"text": "FAIL", "color": "red", "index": 1}
                    }}
                ]
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "short",
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"red","value":None},{"color":"green","value":1}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": "pbs_backup_task_last_status",
                         "legendFormat": "PBS Status", "refId": "A"}]
        },
        {
            "id": 5, "type": "stat", "title": "PBS Laatste Backup",
            "description": "Proxmox Backup Server — tijd geleden sinds laatste backup",
            "gridPos": {"h": 5, "w": 6, "x": 18, "y": 2},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                "graphMode": "none", "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 36, "titleSize": 18}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "s",
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"green","value":None},{"color":"yellow","value":86400},
                        {"color":"orange","value":172800},{"color":"red","value":259200}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": "time() - pbs_backup_task_last_timestamp",
                         "legendFormat": "Geleden", "refId": "A"}]
        },
        header(6, "rclone Backups — FILESERVER", 7),
        {
            "id": 7, "type": "stat", "title": "rclone Status",
            "description": "rclone backup taken — laatste resultaat (1=OK, 0=FAIL)",
            "gridPos": {"h": 5, "w": 8, "x": 0, "y": 9},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                "graphMode": "none", "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 52, "titleSize": 18},
                "mappings": [
                    {"type": "value", "options": {
                        "1": {"text": "OK", "color": "green", "index": 0},
                        "0": {"text": "FAIL", "color": "red", "index": 1}
                    }}
                ]
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "short",
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"red","value":None},{"color":"green","value":1}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": "rclone_backup_job_success",
                         "legendFormat": "{{exported_job}} ({{instance}})", "refId": "A"}]
        },
        {
            "id": 8, "type": "stat", "title": "rclone Laatste Run",
            "description": "rclone — tijd geleden since laatste backup run",
            "gridPos": {"h": 5, "w": 8, "x": 8, "y": 9},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                "graphMode": "none", "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 36, "titleSize": 18}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "s",
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"green","value":None},{"color":"yellow","value":86400},
                        {"color":"orange","value":172800},{"color":"red","value":259200}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": "time() - rclone_backup_job_last_run_timestamp",
                         "legendFormat": "{{exported_job}} geleden", "refId": "A"}]
        },
        {
            "id": 9, "type": "stat", "title": "rclone Duur",
            "description": "rclone — duur van de laatste backup run",
            "gridPos": {"h": 5, "w": 8, "x": 16, "y": 9},
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background",
                "graphMode": "none", "textMode": "value_and_name", "justifyMode": "center",
                "text": {"valueSize": 52, "titleSize": 18}
            },
            "fieldConfig": {
                "defaults": {
                    "unit": "s",
                    "thresholds": {"mode": "absolute", "steps": [
                        {"color":"green","value":None},{"color":"yellow","value":1800},{"color":"orange","value":3600}
                    ]}
                }, "overrides": []
            },
            "targets": [{"expr": "rclone_backup_job_duration_seconds",
                         "legendFormat": "{{exported_job}} duur", "refId": "A"}]
        },
        header(10, "NTFY — Notificaties (VPS)", 14),
        {
            "id": 11, "type": "text", "title": "", "transparent": True,
            "gridPos": {"h": 4, "w": 24, "x": 0, "y": 16},
            "options": {
                "content": "**NTFY** loopt op de VPS (100.125.153.71:2586 — ntfy.hostinglocal.be).\n\nPer-topic monitoring vereist een custom scraper die nog niet geconfigureerd is. Voeg topics toe in de Prometheus scrape config of maak een ntfy-exporter aan om notificatietellingen per topic te zien.",
                "mode": "markdown",
                "code": {"language": "plaintext", "showLineNumbers": False, "showMiniMap": False}
            },
            "fieldConfig": {"defaults": {}, "overrides": []}
        },
        header(12, "Backup Tijdreeks — 7 dagen", 20),
        {
            "id": 13, "type": "timeseries",
            "title": "Backup Jobs — Duur & PBS Opslag",
            "description": "rclone duur, PBS duur en PBS opslaggebruik % over 7 dagen",
            "gridPos": {"h": 14, "w": 24, "x": 0, "y": 22},
            "options": {
                "tooltip": {"mode": "multi", "sort": "desc"},
                "legend": {"displayMode": "table", "placement": "right", "calcs": ["lastNotNull", "mean", "max"]}
            },
            "fieldConfig": {
                "defaults": {"unit": "s", "custom": {"lineWidth": 2, "fillOpacity": 10}},
                "overrides": [
                    {"matcher": {"id": "byName", "options": "PBS Gebruik %"},
                     "properties": [
                         {"id": "unit", "value": "percent"},
                         {"id": "custom.axisPlacement", "value": "right"},
                         {"id": "color", "value": {"fixedColor": "#FF9830", "mode": "fixed"}}
                     ]}
                ]
            },
            "targets": [
                {"expr": "rclone_backup_job_duration_seconds",
                 "legendFormat": "rclone {{exported_job}} duur (s)", "refId": "A"},
                {"expr": "pbs_backup_task_last_duration_seconds",
                 "legendFormat": "PBS backup duur (s)", "refId": "B"},
                {"expr": "pbs_datastore_used_bytes / pbs_datastore_total_bytes * 100",
                 "legendFormat": "PBS Gebruik %", "refId": "C"}
            ]
        }
    ]
}
W(os.path.join(DASH, "notificaties-kiosk.json"), notify)

# ── Infinity datasource ────────────────────────
os.makedirs(DS, exist_ok=True)
with open(os.path.join(DS, "infinity.yml"), 'w', encoding='utf-8') as f:
    f.write("apiVersion: 1\ndatasources:\n  - name: Infinity\n    type: yesoreyeram-infinity-datasource\n    uid: infinity\n    access: proxy\n    isDefault: false\n    jsonData: {}\n")
print("OK: infinity.yml")

print("\nKlaar — 4 dashboards + datasource geschreven.")
