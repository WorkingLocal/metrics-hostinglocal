# Metrics — Hosting Local

Monitoring stack voor het volledige Hosting Local homelab.  
Stack draait op **METRICSSERVER** (Dell OptiPlex 3050 SFF, 192.168.111.18).

## Wat het doet

- **Systeemmonitoring** — CPU, RAM, disk, netwerk, temperaturen via Prometheus + Node Exporter
- **Live dashboards** — Grafana 11.6.2 met provisioned dashboards per node en domein
- **Energie-monitoring** — Beem 300W zonnepanelen, EatonUPS en homelab-verbruik via HAOS
- **Alerting** — Alertmanager stuurt push-notificaties (ntfy) en e-mail bij drempeloverschrijdingen
- **Thermische beveiliging** — thermal-shutdown container voert graceful SSH-shutdown uit bij overkitting
- **Disk health** — smartctl_exporter bewaakt NVMe SMART-status van METRICSSERVER
- **Uptime monitoring** — Uptime Kuma op VPS-HOSTINGLOCAL (apart stack)

## URLs

| Service | URL | Host |
|---------|-----|------|
| Grafana dashboards | https://metrics.hostinglocal.be | METRICSSERVER (via proxy) |
| Uptime Kuma | https://uptime.hostinglocal.be | VPS-HOSTINGLOCAL |
| ntfy notificaties | https://ntfy.hostinglocal.be | VPS-HOSTINGLOCAL |
| Prometheus (intern) | http://192.168.111.18:9090 | METRICSSERVER |
| Alertmanager (intern) | http://192.168.111.18:9093 | METRICSSERVER |

## Stack — METRICSSERVER

| Container | Technologie | Versie | Poort | Netwerk |
|-----------|-------------|--------|-------|---------|
| `prometheus-metrics` | Prometheus | latest | 9090 (host) | host |
| `grafana-metrics` | Grafana | **11.6.2** (vastgepind) | via proxy | proxy |
| `alertmanager-metrics` | Alertmanager | latest | 9093 | proxy + metrics_internal |
| `alertmanager-ntfy` | Flask ntfy bridge | custom | intern | proxy + metrics_internal |
| `thermal-shutdown` | Python SSH | custom | intern | metrics_internal |
| `smartctl-exporter` | smartctl_exporter | latest | 9633 (host) | host |

> **Let op:** Grafana is vastgepind op `11.6.2`. Nooit `latest` gebruiken — Grafana 13 had een 307 redirect loop bug en is schema-incompatibel met 11.x.

## Stack — VPS-HOSTINGLOCAL (apart)

| Container | Technologie | Versie | Poort |
|-----------|-------------|--------|-------|
| `ntfy` | ntfy | latest | 2586 → Caddy |
| `uptime-kuma` | Uptime Kuma | 1 | 3001 (intern) |
| `caddy` | Caddy | alpine | 80/443 |

VPS-HOSTINGLOCAL repo: `/opt/vps-hostinglocal/compose.yml` (beheerd separaat).

## METRICSSERVER hardware

| Component | Waarde |
|-----------|--------|
| Model | Dell OptiPlex 3050 SFF |
| CPU | Intel i5-7500 |
| RAM | 16GB DDR4 |
| Opslag | 256GB NVMe |
| Lokaal IP | 192.168.111.18 |
| Tailscale IP | 100.67.19.40 |
| SSH user | `metrics` (wachtwoord in Vaultwarden → Homelab - Infrastructure) |

## Gemonitorde nodes

| Node | Methode | Tailscale IP | Status |
|------|---------|-------------|--------|
| METRICSSERVER | node_exporter :9100 (host) | localhost | actief |
| VPS-HOSTINGLOCAL | node_exporter :9100 | 100.125.153.71 | actief |
| WINDOWSSERVER2025 | windows_exporter :9182 | 100.92.201.100 | actief |
| NETWORKSERVER | node_exporter :9100 | 100.119.137.54 | actief |
| MEDIASERVER | node_exporter :9100 | 100.111.62.69 | actief |
| AI-NODE-I9 | node_exporter :9100 | 100.126.121.11 | actief |
| AI-NODE-I5 | node_exporter :9100 | 100.78.175.49 | actief |
| TRAVELSERVER | node_exporter :9100 | 100.83.16.76 | actief |
| NUT-SERVER Pi | node_exporter :9100 | 100.97.195.23 | actief |
| HAOS-NUC | Native HA Prometheus `/api/prometheus` :8123 | 192.168.111.75 (LAN) | actief |
| VM-AutoBA | node_exporter :9100 | 100.107.82.21 | actief |
| VM-AI-Engine | node_exporter :9100 | 100.80.180.55 | actief |
| VM-ADGUARD | node_exporter :9100 | 100.121.177.76 | actief |
| VM-NPM | node_exporter :9100 | 100.75.230.22 | actief |
| VM-NETBOX | node_exporter :9100 | 100.122.166.117 | actief |
| VM-PLEX | node_exporter :9100 | 100.83.181.85 | actief |
| VM-IMMICH | node_exporter :9100 | 100.75.33.124 | actief |
| VM-APPS | node_exporter :9100 | 100.97.124.46 | actief |
| VM-OPENCLAW | node_exporter :9100 | 100.92.71.9 | actief |
| FILESERVER | node_exporter Docker :9100 | 100.72.50.41 | actief |
| UNIFI-GATEWAY | SNMP via snmp-exporter (NETWORKSERVER :9116) | 192.168.111.1 | actief |

## Repository structuur

```
metrics-hostinglocal/
├── compose.hostinglocal.yml        # Hoofdstack: Prometheus + Grafana + Alertmanager + ntfy + thermal-shutdown
├── prometheus.hostinglocal.yml     # Scrape targets — wordt geüpload als prometheus.yml op METRICSSERVER
├── alert.rules.yml                 # Alerting regels (CPU, RAM, disk, InstanceDown)
├── alertmanager.yml                # ntfy + e-mail routing
├── alertmanager-ntfy/              # Flask bridge: Alertmanager webhook → ntfy push
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
├── thermal-shutdown/               # Python SSH-shutdown service bij hoge temperatuur
│   ├── Dockerfile
│   ├── app.py
│   ├── hosts.yml                   # SSH targets (Tailscale IP + user per node)
│   └── requirements.txt
├── snmp/                           # SNMP Exporter voor Unifi Gateway
│   └── snmp-exporter.yml
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── prometheus.yml      # Prometheus datasource (via host.docker.internal)
│       └── dashboards/
│           ├── dashboards.yml      # Dashboard provider config
│           ├── energie.json        # Energie & Zonnepanelen (Beem + UPS + Homelab) ☀️
│           ├── overview.json       # Homelab Overview (alle nodes) 🖥️
│           ├── disk-overview.json  # Disk Overview — alle schijven 🖥️
│           ├── temperatures.json   # Host Temperatures (alle nodes)
│           ├── ai-nodes.json       # AI Nodes Load Monitor
│           ├── adguard-home.json   # AdGuard Home DNS dashboard
│           ├── unifi.json          # Unifi Gateway (SNMP)
│           ├── windows-server.json # Windows Server 2025
│           ├── vps.json            # VPS-WORKINGLOCAL
│           ├── haos.json           # HAOS Intel NUC (native HA Prometheus)
│           ├── fileserver.json     # FILESERVER Synology DS423+
│           └── ...
└── docs/
    ├── setup.md                    # Installatie & deploy handleiding
    ├── technisch.md                # Architectuur & configuratie details
    ├── howto.md                    # Operationele handleiding
    ├── alerts.md                   # Alert regels & drempelwaarden
    └── ntfy-integrations.md        # ntfy configuratie per service
```

> 🖥️ = geschikt voor signage display (Xibo / kiosk mode)

## Deploy

De server `/opt/metrics-hostinglocal/` is een git clone van dit repo (geconfigureerd 2026-06-12).

**Workflow:**
```bash
# 1. Push vanuit laptop
git push origin main

# 2. Op METRICSSERVER (SSH: metrics@100.67.19.40)
cd /opt/metrics-hostinglocal && git pull
docker compose -f compose.hostinglocal.yml restart grafana

# Voor Prometheus config-wijziging (hot-reload):
curl -s -X POST http://192.168.111.18:9090/-/reload
# Of volledige herstart:
docker compose -f compose.hostinglocal.yml up -d prometheus
```

SSH hostkey METRICSSERVER: `ssh-ed25519 255 SHA256:OjbfvxtNnimyojTDKvh58i24tTCEZdafj98DljzwBsU`  
Credentials: Vaultwarden → "METRICSSERVER — metrics user" (metrics@192.168.111.18 / 100.67.19.40)

## Grafana

- URL: https://metrics.hostinglocal.be (of http://192.168.111.18:3000 intern)
- Gebruiker: `admin`
- Wachtwoord: zie Vaultwarden → Homelab - Infrastructure → "METRICSSERVER — Grafana"

### Dashboards

| Dashboard | UID | Bestand | Signage |
|-----------|-----|---------|---------|
| Energie & Zonnepanelen | energie-zonnepanelen | `energie.json` | — |
| Homelab Overview | homelab-overview-hl | `overview.json` | ✅ |
| Disk Overview | disk-overview-hl | `disk-overview.json` | ✅ |
| Host Temperatures | host-temperatures-hl | `temperatures.json` | — |
| AI Nodes Load Monitor | 2ca2c5e5-... | `ai-nodes.json` | — |
| AdGuard Home DNS | adguard-home-hostinglocal | `adguard-home.json` | — |
| Unifi Gateway | unifi-gateway-hl | `unifi.json` | — |
| Windows Server 2025 | windows-server-hl | `windows-server.json` | — |
| VPS — Workinglocal | vps-workinglocal-hl | `vps.json` | — |
| HAOS — Intel NUC | haos-nuc-hl | `haos.json` | — |
| FILESERVER Synology | fileserver-hl | `fileserver.json` | — |
| AI Engine — Claude Credits | litellm-credits | `litellm-credits.json` | — |

Alle dashboards worden automatisch provisioned vanuit `grafana/provisioning/dashboards/`.

### Datasources

| Datasource | UID | Bestand | Beschrijving |
|-----------|-----|---------|--------------|
| Prometheus | prometheus | `datasources/prometheus.yml` | Prometheus via host.docker.internal |
| NetBox (Infinity) | infinity-netbox | `datasources/infinity.yml` | NetBox REST API |
| LiteLLM (Infinity) | infinity-litellm | `datasources/litellm.yml` | LiteLLM spend/budget API (bearer: HostingLocal2024) |

## Energie-monitoring (HAOS)

HAOS exporteert alle numerieke entiteiten via de native Prometheus-integratie naar `/api/prometheus`.
Prometheus scrapet HAOS-NUC elke 120s via lokaal netwerk (192.168.111.75:8123).
Bearer token: Vaultwarden → Home Assistant → "HAOS - Long-lived API Token".

| Entity | Beschrijving |
|--------|-------------|
| `sensor.beem_energy_thomas_vandromme_current_power` | Beem 300W productie in W |
| `sensor.beem_energy_thomas_vandromme_daily_energy` | Dagproductie in Wh |
| `sensor.beem_energy_thomas_vandromme_monthly_energy` | Maandproductie in Wh |
| `sensor.beem_zonnepanelen_kwh_totaal` | Cumulatieve productie kWh |
| `sensor.eatonups_current_real_power` | UPS real power in W |
| `sensor.eatonups_battery_charge` | Batterijlading in % |
| `sensor.eatonups_load` | UPS belasting in % |
| `sensor.homelab_verbruik_kwh_totaal` | Cumulatief homelab-verbruik kWh |

## Thermal Shutdown

De `thermal-shutdown` container reageert op Alertmanager webhooks en voert SSH-shutdown uit op fysieke nodes bij kritieke temperatuuralerts.

SSH key: `/root/.ssh/thermal_shutdown` op METRICSSERVER.  
Publieke sleutel gedistribueerd naar (mei 2025): AI-NODE-I9, AI-NODE-I5, NETWORKSERVER, MEDIASERVER, NUT-SERVER, HAOS-NUC, WINDOWSSERVER2025.  
Nog te doen: FILESERVER (SSH poort 221), TRAVELSERVER (offline gehad).

Hosts config: `thermal-shutdown/hosts.yml`

## Alerts

| Alert | Drempel | Ernst | Kanaal |
|-------|---------|-------|--------|
| InstanceDown | 2 minuten offline | critical | ntfy + email |
| HighCpuUsage | >80% gedurende 5 min | warning | ntfy |
| HighMemoryUsage | >80% gedurende 5 min | warning | ntfy |
| NvmeDiskUsageHigh | >80% gedurende 5 min | warning | ntfy |
| NvmeDiskUsageCritical | >90% gedurende 1 min | critical | ntfy + email |

## ntfy

Server: `https://ntfy.hostinglocal.be` (VPS-HOSTINGLOCAL 100.125.153.71)  
Topic: `homelab`  
Publisher token: Vaultwarden → Homelab - Infrastructure → "ntfy — publisher token homelab"

## Gerelateerde repositories

| Repo | Inhoud |
|------|--------|
| [infra-hostinglocal](../infra-hostinglocal) | Infra-documentatie + homelab_finance DB |
| [vps-workinglocal](../vps-workinglocal) | VPS-WORKINGLOCAL setup |
