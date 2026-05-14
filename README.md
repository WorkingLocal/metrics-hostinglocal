# Metrics — Working Local

Monitoring stack voor het volledige Hosting Local homelab.

## Wat het doet

- **Systeemmonitoring** — CPU, RAM, disk, netwerk via Prometheus + Node Exporter
- **Live dashboards** — Grafana met Node Exporter Full, Windows Exporter en AI Nodes Load Monitor dashboards
- **Alerting** — Alertmanager stuurt e-mailmeldingen bij drempeloverschrijdingen
- **Uptime monitoring** — Uptime Kuma bewaakt alle webapplicaties en services

## URLs

| Service | URL |
|---------|-----|
| Grafana dashboards | https://metrics.workinglocal.be |
| Uptime Kuma status | https://uptime.workinglocal.be |
| Prometheus (intern) | http://VPS:9090 |

## Stack

| Onderdeel | Technologie | Poort |
|-----------|-------------|-------|
| Metrics scraping | Prometheus | 9090 (host) |
| Dashboards | Grafana | 3000 (via Traefik) |
| Alerting | Alertmanager | 9093 |
| Uptime monitoring | Uptime Kuma | 3001 (via Traefik) |

## Gemonitorde nodes

| Node | Methode | Tailscale IP | Status |
|------|---------|-------------|--------|
| VPS-WORKINGLOCAL | node_exporter (host) | 100.107.226.24 | actief |
| WINDOWSSERVER2025 | windows_exporter :9182 | 100.92.201.100 | actief |
| NETWORKSERVER | node_exporter :9100 | 100.119.137.54 | actief |
| MEDIASERVER | node_exporter :9100 | 100.111.62.69 | actief |
| VM-AutoBA | node_exporter Docker :9100 | 100.107.82.21 | actief |
| VM-AI-Engine | node_exporter :9100 | 100.80.180.55 | actief |
| VM-ADGUARD | node_exporter :9100 | 100.121.177.76 | actief |
| VM-NPM | node_exporter :9100 | 100.75.230.22 | actief |
| VM-NETBOX | node_exporter :9100 | 100.122.166.117 | actief |
| VM-PLEX | node_exporter :9100 | 100.83.181.85 | actief |
| VM-IMMICH | node_exporter :9100 | 100.75.33.124 | actief |
| VM-APPS | node_exporter :9100 | 100.97.124.46 | actief |
| AI-NODE-I9 | node_exporter :9100 | 100.126.121.11 | actief |
| AI-NODE-I5 | node_exporter :9100 | 100.78.175.49 | actief |
| NUT-SERVER Pi | node_exporter :9100 | 100.97.195.23 | actief |
| HAOS-NUC | Netdata Prometheus export :19999 | 100.109.230.93 | actief |

## Repository structuur

```
metrics-workinglocal/
├── docker-compose.yml              # Grafana + Prometheus + Alertmanager + Uptime Kuma
├── prometheus.yml                  # Scrape targets (alle Tailscale nodes)
├── alert.rules.yml                 # Alerting regels (CPU, RAM, disk, uptime)
├── alertmanager.yml                # E-mail notificaties via Hostinger SMTP
├── deploy.sh                       # Volledige deploy naar VPS
├── deploy-config.sh                # Alleen config bijwerken (zonder redeploy)
├── install-node-exporter.sh        # Installatiescript voor Linux nodes
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── prometheus.yml      # Prometheus datasource
│       └── dashboards/
│           └── dashboards.yml      # Dashboard provider config
└── docs/
    ├── setup.md
    ├── alerts.md
    ├── howto.md
    └── technisch.md
```

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
curl -sL https://raw.githubusercontent.com/WorkingLocal/metrics-workinglocal/main/install-node-exporter.sh | bash
```

### windows_exporter op Windows Server

Download en installeer de MSI van [windows_exporter releases](https://github.com/prometheus-community/windows_exporter/releases).
Default poort: 9182.

## Grafana credentials

- URL: https://metrics.workinglocal.be
- Gebruiker: `admin`
- Wachtwoord: zie `.env` op VPS (`/data/coolify/services/metrics-stack/.env`)

## Grafana dashboards

| Dashboard | UID | URL |
|-----------|-----|-----|
| Node Exporter Full | (Grafana ID 1860) | https://metrics.workinglocal.be |
| Windows Exporter | (Grafana ID 14694) | https://metrics.workinglocal.be |
| AI Nodes Load Monitor | 2ca2c5e5-ca9a-49e7-8010-017d804f4678 | https://metrics.workinglocal.be/d/2ca2c5e5-ca9a-49e7-8010-017d804f4678/ai-nodes-efbfbd-load-monitor |

## Uptime Kuma credentials

- URL: https://uptime.workinglocal.be
- Gebruiker: `admin`
- Wachtwoord: zie Grafana ADMIN_PASSWORD (zelfde wachtwoord)

## Alerts

Alerts worden verstuurd via e-mail (`info@workinglocal.be` → `thomas@workinglocal.be`).

| Alert | Drempel | Ernst |
|-------|---------|-------|
| InstanceDown | 2 minuten offline | critical |
| HighCpuUsage | >80% gedurende 5 min | warning |
| HighMemoryUsage | >80% gedurende 5 min | warning |
| NvmeDiskUsageHigh | /dev/nvme* >80% gedurende 5 min | warning |
| NvmeDiskUsageCritical | /dev/nvme* >90% gedurende 1 min | critical |

## DNS

| Record | Type | Waarde |
|--------|------|--------|
| metrics.workinglocal.be | A | 23.94.220.181 |
| uptime.workinglocal.be | A | 23.94.220.181 |


## Gerelateerde repositories

| Repo | Inhoud |
|------|--------|
| [vps-workinglocal](https://github.com/WorkingLocal/vps-workinglocal) | Server setup & infrastructuur |
| [odoo-workinglocal](https://github.com/WorkingLocal/odoo-workinglocal) | Odoo CE + coworking addon |
| [netdata-haos-addon](https://github.com/WorkingLocal/netdata-haos-addon) | Netdata HAOS add-on (Prometheus export voor HAOS-NUC) |
