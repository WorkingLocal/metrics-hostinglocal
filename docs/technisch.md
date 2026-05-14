# Technische documentatie — Metrics Stack

## Architectuur

```
Internet
    │
    └── Traefik (coolify-proxy, VPS 23.94.220.181)
         ├── metrics.workinglocal.be → grafana-metrics:3000
         └── uptime.workinglocal.be  → uptime-kuma-metrics:3001

VPS (host network)
    ├── prometheus-metrics :9090   — scrapet alle nodes via Tailscale
    ├── alertmanager-metrics :9093 — e-mail routing
    ├── node_exporter :9100        — VPS systeemmetrics
    └── Docker bridge (metrics_monitoring)
         ├── grafana-metrics
         ├── alertmanager-metrics
         └── uptime-kuma-metrics

Tailscale nodes (geschraped door Prometheus)
    ├── 100.92.201.100:9182   — WINDOWSSERVER2025 (windows_exporter)
    ├── 100.119.137.54:9100   — NETWORKSERVER (node_exporter systemd)
    ├── 100.111.62.69:9100    — MEDIASERVER (node_exporter systemd)
    ├── 100.107.82.21:9100    — VM-AutoBA (node_exporter Docker)
    ├── 100.80.180.55:9100    — VM-AI-Engine (node_exporter systemd)
    ├── 100.121.177.76:9100   — VM-ADGUARD (node_exporter systemd)
    ├── 100.75.230.22:9100    — VM-NPM (node_exporter systemd)
    └── 100.122.166.117:9100  — VM-NETBOX (node_exporter systemd)
    ├── 100.83.181.85:9100    — VM-PLEX (node_exporter systemd)
    ├── 100.75.33.124:9100    — VM-IMMICH (node_exporter systemd)
    ├── 100.97.124.46:9100    — VM-APPS (node_exporter systemd)
    ├── 100.97.195.23:9100    — NUT-SERVER Pi (node_exporter systemd, arm64)
    ├── 100.109.230.93:19999  — HAOS-NUC (Netdata /api/v1/allmetrics)
    ├── 100.126.121.11:9100   — AI-NODE-I9 (node_exporter)
    └── 100.78.175.49:9100    — AI-NODE-I5 (node_exporter)
```

## Docker compose netwerken

| Container | Netwerken | Reden |
|-----------|-----------|-------|
| prometheus-metrics | host | Tailscale IPs bereiken |
| grafana-metrics | monitoring + traefik (b5qxgv0vprkhgiioth9yk0fj) | Prometheus via host-gateway, Traefik routing |
| alertmanager-metrics | monitoring | Intern bereikbaar voor Prometheus |
| uptime-kuma-metrics | monitoring + traefik | Grafana intern bereiken, Traefik routing |

**Belangrijk:** Grafana gebruikt `extra_hosts: host.docker.internal:host-gateway` om Prometheus op `localhost:9090` te bereiken.

## Prometheus configuratie

- Config: `/data/coolify/services/metrics-stack/prometheus.yml`
- Scrape interval: 15s
- Data retentie: 30 dagen
- Hot reload: `POST http://localhost:9090/-/reload`

## Alertmanager configuratie

- Config: `/data/coolify/services/metrics-stack/alertmanager.yml`
- Geen hot reload — vereist `docker restart alertmanager-metrics`
- Routing: warnings (12h repeat) vs critical (1h repeat)
- Grouping: per `alertname + instance`

## Alert regels

Zie [alerts.md](alerts.md) voor de volledige tabel.

Prometheus haalt regels op via `/data/coolify/services/metrics-stack/alert.rules.yml`.
Hot reload via `POST /-/reload`.

## Grafana

- Image: `grafana/grafana:latest`
- Data: Docker volume `metrics_grafana_data`
- Provisioning: datasources + dashboard provider via bind mounts
- SMTP: via `GF_SMTP_*` environment variabelen (uit `.env`)

## Uptime Kuma

- Image: `louislam/uptime-kuma:2` (v2.2.1)
- Data: Docker volume `metrics_uptime_kuma_data`
- Database: SQLite op `/app/data/kuma.db`
- **Hairpin NAT:** Grafana-monitor checkt intern `http://grafana-metrics:3000/api/health` — publieke URL geeft intermittente 504 als check vanop dezelfde VPS loopt

## VPS locatie

```
/data/coolify/services/metrics-stack/
├── docker-compose.yml
├── prometheus.yml
├── alert.rules.yml
├── alertmanager.yml
├── .env                    # GRAFANA_ADMIN_PASSWORD + SMTP_PASSWORD
└── grafana/
    └── provisioning/
        ├── datasources/prometheus.yml
        └── dashboards/dashboards.yml
```

## Credentials

| Service | Gebruiker | Wachtwoord |
|---------|-----------|-----------|
| Grafana | admin | zie `.env` GRAFANA_ADMIN_PASSWORD |
| Uptime Kuma | admin | zelfde als Grafana |
| Alertmanager SMTP | info@workinglocal.be | zie `.env` SMTP_PASSWORD |

## node_exporter installaties per node

| Node | Methode | Architectuur | Tailscale IP |
|------|---------|-------------|-------------|
| VPS-WORKINGLOCAL | systemd service | amd64 | 100.107.226.24 |
| NETWORKSERVER | systemd service | amd64 | 100.119.137.54 |
| MEDIASERVER | systemd service | amd64 | 100.111.62.69 |
| VM-AutoBA | Docker container (host network) | amd64 | 100.107.82.21 |
| VM-AI-Engine | systemd service | amd64 | 100.80.180.55 |
| VM-ADGUARD | systemd service | amd64 | 100.121.177.76 |
| VM-PLEX | systemd service | amd64 | 100.83.181.85 |
| VM-IMMICH | systemd service | amd64 | 100.75.33.124 |
| VM-APPS | systemd service | amd64 | 100.97.124.46 |
| NUT-SERVER Pi | systemd service | arm64 | 100.97.195.23 |
| AI-NODE-I9 | systemd service | amd64 | 100.126.121.11 |
| AI-NODE-I5 | systemd service | amd64 | 100.78.175.49 |
| HAOS-NUC | Netdata add-on (Prometheus export) | amd64 | 100.109.230.93 |
| Windows Server | windows_exporter MSI :9182 | amd64 | 100.92.201.100 |
