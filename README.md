# Metrics — Hosting Local

Monitoring stack voor het volledige Hosting Local homelab.

## Wat het doet

- **Systeemmonitoring** — CPU, RAM, disk, netwerk, **temperaturen** via Prometheus + Node Exporter
- **Live dashboards** — Grafana met Node Exporter Full, Windows Exporter, AI Nodes Load Monitor en Host Temperatures dashboards
- **Alerting** — Alertmanager stuurt e-mailmeldingen bij drempeloverschrijdingen
- **Uptime monitoring** — Uptime Kuma bewaakt alle webapplicaties en services

## URLs

| Service | URL |
|---------|-----|
| Grafana dashboards | https://metrics.hostinglocal.be |
| Uptime Kuma status | https://uptime.hostinglocal.be |
| Prometheus (intern) | http://VPS:9090 |

## Stack

| Onderdeel | Technologie | Versie | Poort |
|-----------|-------------|--------|-------|
| Metrics scraping | Prometheus | latest | 9090 (host) |
| Dashboards | Grafana | **11.6.2** (vastgepind) | 3000 (via Traefik) |
| Alerting | Alertmanager | latest | 9093 |
| Uptime monitoring | Uptime Kuma | 2 | 3001 (via Traefik) |

> **Let op:** Grafana is vastgepind op `11.6.2`. Gebruik nooit `latest` — Grafana 13 had een 307 redirect loop bug en is incompatibel met het databaseschema van 11.x.

## Gemonitorde nodes

| Node | Methode | Tailscale IP | Status |
|------|---------|-------------|--------|
| VPS-WORKINGLOCAL | node_exporter :9100 | 100.107.226.24 | actief |
| WINDOWSSERVER2025 | windows_exporter :9182 | 100.92.201.100 | actief |
| NETWORKSERVER | node_exporter :9100 | 100.119.137.54 | actief |
| MEDIASERVER | node_exporter :9100 | 100.111.62.69 | actief |
| AI-NODE-I9 | node_exporter :9100 | 100.126.121.11 | actief |
| AI-NODE-I5 | node_exporter :9100 | 100.78.175.49 | actief |
| TRAVELSERVER | node_exporter :9100 | 100.83.16.76 | actief |
| NUT-SERVER Pi | node_exporter :9100 | 100.97.195.23 | actief |
| HAOS-NUC | Netdata Prometheus export :19999 | 100.109.230.93 | actief |
| VM-AutoBA | node_exporter Docker :9100 | 100.107.82.21 | actief |
| VM-AI-Engine | node_exporter :9100 | 100.80.180.55 | actief |
| VM-ADGUARD | node_exporter :9100 | 100.121.177.76 | actief |
| VM-NPM | node_exporter :9100 | 100.75.230.22 | actief |
| VM-NETBOX | node_exporter :9100 | 100.122.166.117 | actief |
| VM-PLEX | node_exporter :9100 | 100.83.181.85 | actief |
| VM-IMMICH | node_exporter :9100 | 100.75.33.124 | actief |
| VM-APPS | node_exporter :9100 | 100.97.124.46 | actief |
| VM-OPENCLAW | node_exporter :9100 | 100.92.71.9 | actief |
| FILESERVER | node_exporter Docker :9100 | 100.72.50.41 | actief |

## Repository structuur

```
metrics-hostinglocal/
├── docker-compose.yml              # Grafana 11.6.2 + Prometheus + Alertmanager + Uptime Kuma
├── prometheus.yml                  # Scrape targets (alle Tailscale nodes)
├── alert.rules.yml                 # Alerting regels (CPU, RAM, disk, uptime)
├── alertmanager.yml                # E-mail notificaties via Hostinger SMTP
├── deploy.sh                       # Volledige deploy naar VPS
├── deploy-config.sh                # Alleen config bijwerken (zonder redeploy)
├── install-node-exporter.sh        # Installatiescript voor Linux nodes (hwmon/thermal/textfile flags)
├── install-lm-sensors.sh           # lm-sensors installeren voor CPU-sensornamen
├── scripts/
│   ├── intel-gpu-temp-collector.sh # Textfile collector voor Intel i915/xe GPU-temp
│   └── deploy-intel-gpu-temp.sh    # Deployscript voor GPU-temp collector
├── windows-temp/
│   └── setup.ps1                   # windows_exporter thermalzone collector inschakelen
├── snmp/
│   ├── docker-compose.yml          # SNMP Exporter container (op NETWORKSERVER)
│   ├── install-snmp-exporter.sh    # Installatiescript SNMP Exporter
│   └── deploy.sh                   # Deployscript SNMP stack
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── prometheus.yml      # Prometheus datasource
│       └── dashboards/
│           ├── dashboards.yml      # Dashboard provider config
│           ├── overview.json       # Homelab Overview (CPU/RAM/disk/status alle nodes) 🖥️
│           ├── cpu-cores.json      # CPU Cores — alle cores alle nodes op één pagina
│           ├── disk-overview.json  # Disk Overview — alle schijven + vrije ruimte 🖥️
│           ├── temperatures.json   # Host Temperatures dashboard (alle nodes)
│           ├── ai-nodes.json       # AI Nodes Load Monitor dashboard
│           ├── adguard-home.json   # AdGuard Home DNS dashboard
│           ├── unifi.json          # Unifi Gateway (SNMP — traffic + interface status)
│           ├── windows-server.json # Windows Server 2025 (CPU/RAM/disk/netwerk)
│           ├── vps.json            # VPS-WORKINGLOCAL (CPU/RAM/disk/netwerk/systeem)
│           ├── haos.json           # HAOS Intel NUC (via Netdata Prometheus export)
│           └── fileserver.json     # FILESERVER — Synology DS423+ (node_exporter Docker)
└── docs/
    ├── setup.md
    ├── alerts.md
    ├── howto.md
    └── technisch.md
```

> 🖥️ = geschikt voor signage display (Xibo / kiosk mode)

## Deployment

### Eerste installatie op VPS

```bash
# Volledige deploy (kopieert alle bestanden naar VPS)
bash deploy.sh --smtp-password <wachtwoord>

# Op VPS: stack starten
cd /data/coolify/services/metrics-stack
docker compose up -d
```

### Config bijwerken

```bash
bash deploy-config.sh --smtp-password <wachtwoord>
```

### node_exporter installeren op Linux node

```bash
# SSH naar de node en uitvoeren als root:
bash install-node-exporter.sh
```

Installeert node_exporter met `--collector.hwmon`, `--collector.thermal_zone` en `--collector.textfile.directory` voor temperatuurmonitoring.

### lm-sensors installeren (voor CPU-sensornamen)

```bash
bash install-lm-sensors.sh
```

### windows_exporter op Windows Server

Download en installeer de MSI van [windows_exporter releases](https://github.com/prometheus-community/windows_exporter/releases).
Thermalzone collector inschakelen: `bash windows-temp/setup.ps1` (PowerShell als Administrator).

## Grafana

- URL: https://metrics.hostinglocal.be
- Gebruiker: `admin`
- Wachtwoord: zie `.env` op VPS (`/data/coolify/services/metrics-stack/.env`)

### Dashboards

| Dashboard | UID | Bestand | Signage |
|-----------|-----|---------|---------|
| Node Exporter Full | (Grafana ID 1860) | Importeren via UI of API | — |
| AI Nodes Load Monitor | 2ca2c5e5-ca9a-49e7-8010-017d804f4678 | `ai-nodes.json` | — |
| Host Temperatures | host-temperatures-hl | `temperatures.json` | — |
| AdGuard Home DNS Monitor | adguard-home-hostinglocal | `adguard-home.json` | — |
| Unifi Gateway | unifi-gateway-hl | `unifi.json` | — |
| Windows Server 2025 | windows-server-hl | `windows-server.json` | — |
| Homelab Overview | homelab-overview-hl | `overview.json` | ✅ |
| CPU Cores — Alle Nodes | cpu-cores-hl | `cpu-cores.json` | — |
| Disk Overview — Alle Nodes | disk-overview-hl | `disk-overview.json` | ✅ |
| VPS — Workinglocal | vps-workinglocal-hl | `vps.json` | — |
| HAOS — Intel NUC | haos-nuc-hl | `haos.json` | — |
| NETWORKSERVER | networkserver-hl | `networkserver.json` | — |
| FILESERVER — Synology DS423+ | fileserver-hl | `fileserver.json` | — |

Bij Grafana volume-reset: zie `docs/howto.md` voor het her-importeren van Node Exporter Full via de Grafana API.
Alle andere dashboards worden automatisch provisioned uit `/etc/grafana/provisioning/dashboards/`.

### Signage / Kiosk mode

Dashboards geschikt voor signage display (Xibo, browser, TV):

```
# Volledig dashboard zonder navigatiebalk (kiosk mode):
https://metrics.hostinglocal.be/d/homelab-overview-hl/homelab-overview?kiosk=tv
https://metrics.hostinglocal.be/d/disk-overview-hl/disk-overview-alle-nodes?kiosk=tv

# Enkelvoudig panel embedden (voor Xibo layout):
https://metrics.hostinglocal.be/d-solo/homelab-overview-hl/homelab-overview?panelId=11&kiosk
```

**Grafana Playlist** (automatisch wisselen tussen dashboards):
Grafana → Dashboards → Playlists → New playlist → voeg gewenste dashboards toe → stel interval in.
Gebruik de playlist URL + `?kiosk=tv` voor schermloze weergave.

**Xibo integratie:** voeg een "Webpage" widget toe in Xibo met de kiosk URL. Stel in Xibo de looptijd per layout in op bv. 60s. Vergeet niet om Grafana's auto-refresh (`1m`) te verifiëren via de dashboard `refresh` instelling.

## Uptime Kuma

- URL: https://uptime.hostinglocal.be
- Gebruiker: `admin`
- Wachtwoord: zelfde als Grafana

## Cloudflare + Traefik

Grafana zit achter Cloudflare (Full SSL mode). Gebruik **geen** `redirect-to-https` middleware in Traefik — dit veroorzaakt een 307 redirect loop. Cloudflare "Always Use HTTPS" handelt de HTTP→HTTPS redirect af op de edge.

## Alerts

| Alert | Drempel | Ernst |
|-------|---------|-------|
| InstanceDown | 2 minuten offline | critical |
| HighCpuUsage | >80% gedurende 5 min | warning |
| HighMemoryUsage | >80% gedurende 5 min | warning |
| NvmeDiskUsageHigh | /dev/nvme* >80% gedurende 5 min | warning |
| NvmeDiskUsageCritical | /dev/nvme* >90% gedurende 1 min | critical |

## Gerelateerde repositories

| Repo | Inhoud |
|------|--------|
| [vps-workinglocal](../vps-workinglocal) | Server setup & infrastructuur |
| [netdata-haos-addon](../netdata-haos-addon) | Netdata HAOS add-on (Prometheus export voor HAOS-NUC) |
