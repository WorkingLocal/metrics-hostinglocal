# Technische documentatie — Metrics Stack

## Architectuur

```
Internet
    │
    └── Cloudflare (Always Use HTTPS — geen Traefik redirect-to-https middleware!)
         └── Traefik (coolify-proxy, VPS 23.94.220.181)
              ├── metrics.hostinglocal.be → grafana-metrics:3000
              └── uptime.hostinglocal.be  → uptime-kuma-metrics:3001

VPS (host network)
    ├── prometheus-metrics :9090   — scrapet alle nodes via Tailscale
    ├── alertmanager-metrics :9093 — e-mail routing
    ├── node_exporter :9100        — VPS systeemmetrics
    └── Docker bridge (metrics_monitoring)
         ├── grafana-metrics (11.6.2)
         ├── alertmanager-metrics
         └── uptime-kuma-metrics

Tailscale nodes (geschraped door Prometheus)
    ├── 100.92.201.100:9182   — WINDOWSSERVER2025 (windows_exporter)
    ├── 100.119.137.54:9100   — NETWORKSERVER (node_exporter systemd)
    ├── 100.111.62.69:9100    — MEDIASERVER (node_exporter systemd)
    ├── 100.126.121.11:9100   — AI-NODE-I9 (node_exporter systemd)
    ├── 100.78.175.49:9100    — AI-NODE-I5 (node_exporter systemd)
    ├── 100.83.16.76:9100     — TRAVELSERVER (node_exporter Docker app, TrueNAS SCALE)
    ├── 100.97.195.23:9100    — NUT-SERVER Pi (node_exporter systemd, armv7)
    ├── 100.107.82.21:9100    — VM-AutoBA (node_exporter Docker)
    ├── 100.80.180.55:9100    — VM-AI-Engine (node_exporter systemd)
    ├── 100.121.177.76:9100   — VM-ADGUARD (node_exporter systemd)
    ├── 100.75.230.22:9100    — VM-NPM (node_exporter systemd)
    ├── 100.122.166.117:9100  — VM-NETBOX (node_exporter systemd)
    ├── 100.83.181.85:9100    — VM-PLEX (node_exporter systemd)
    ├── 100.75.33.124:9100    — VM-IMMICH (node_exporter systemd)
    ├── 100.97.124.46:9100    — VM-APPS (node_exporter systemd)
    └── 100.109.230.93:19999  — HAOS-NUC (Netdata /api/v1/allmetrics)
```

## Docker compose netwerken

| Container | Netwerken | Reden |
|-----------|-----------|-------|
| prometheus-metrics | host | Tailscale IPs bereiken |
| grafana-metrics | monitoring + traefik (b5qxgv0vprkhgiioth9yk0fj) | Prometheus via host-gateway, Traefik routing |
| alertmanager-metrics | monitoring | Intern bereikbaar voor Prometheus |
| uptime-kuma-metrics | monitoring + traefik | Grafana intern bereiken, Traefik routing |

**Belangrijk:** Grafana gebruikt `extra_hosts: host.docker.internal:host-gateway` om Prometheus op `localhost:9090` te bereiken.

## Grafana

- Image: `grafana/grafana:11.6.2` — **vastgepind, nooit `latest`**
- Data: Docker volume `metrics_grafana_data`
- Provisioning: datasources + dashboard provider via bind mounts
- SMTP: via `GF_SMTP_*` environment variabelen (uit `.env`)
- `GF_SERVER_ROOT_URL`: `https://metrics.hostinglocal.be`

### Cloudflare + Traefik

Grafana zit achter Cloudflare (Full SSL mode, "Always Use HTTPS" ingeschakeld).
**Geen** `redirect-to-https` Traefik middleware gebruiken — dit veroorzaakt een 307 redirect loop omdat Cloudflare soms HTTP naar de origin stuurt. Cloudflare handelt HTTP→HTTPS zelf af op de edge.

### Grafana volume-reset procedure

Als het Grafana volume gereset moet worden (bv. na downgrade):
```bash
docker compose stop grafana
docker rm grafana-metrics
docker volume rm metrics_grafana_data
docker compose up -d grafana
# Wacht 30s, importeer daarna dashboards via API of UI
```
Provisioned dashboards (temperatures.json, ai-nodes.json, adguard-home.json) verschijnen automatisch.
Node Exporter Full (1860) en Windows Exporter (14694) moeten opnieuw geïmporteerd worden — zie howto.md.

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

## Temperatuurmonitoring

### node_exporter flags

Alle Linux nodes hebben node_exporter met deze extra flags (mei 2026):
```
--collector.hwmon
--collector.thermal_zone
--collector.textfile.directory=/var/lib/node_exporter/textfile_collector
```

### Temperatuur metrics per host

| Host | Metric | Chip | Sensor |
|------|--------|------|--------|
| AI-NODE-I9, AI-NODE-I5, NETWORKSERVER, MEDIASERVER, TRAVELSERVER | `node_hwmon_temp_celsius` | `platform_coretemp_0` | `temp1` (Package) |
| NUT-SERVER Pi | `node_hwmon_temp_celsius` | `thermal_thermal_zone0` | `temp0` |
| WINDOWSSERVER2025 | `windows_thermalzone_temperature_kelvin - 273.15` | — | WMI (geen data op Hyper-V) |

### Intel GPU temperatuur

Intel iGPU is aanwezig op AI-NODE-I9 (Iris Xe), AI-NODE-I5, MEDIASERVER (Iris Plus 655) maar **geen van de hosts exposed i915/xe hwmon**.
- Script: `scripts/intel-gpu-temp-collector.sh` — textfile collector die `/sys/class/hwmon/hwmon*/name` doorzoekt op `i915` of `xe`
- Metric: `intel_gpu_temperature_celsius{instance="..."}`
- Op huidige hosts: **geen data** (hwmon interface niet beschikbaar zonder i915 debugging kernel flags)

### lm-sensors

Geïnstalleerd op: AI-NODE-I9, AI-NODE-I5, NETWORKSERVER, MEDIASERVER, NUT-SERVER.
Installeren: `bash install-lm-sensors.sh`

## VPS bestandsstructuur

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
        └── dashboards/
            ├── dashboards.yml
            ├── temperatures.json
            ├── ai-nodes.json
            └── adguard-home.json
```

## Credentials

| Service | Gebruiker | Wachtwoord |
|---------|-----------|-----------|
| Grafana | admin | zie `.env` GRAFANA_ADMIN_PASSWORD |
| Uptime Kuma | admin | zelfde als Grafana |
| Alertmanager SMTP | info@workinglocal.be | zie `.env` SMTP_PASSWORD |

## node_exporter installaties per node

| Node | Methode | Architectuur | Tailscale IP | Temp |
|------|---------|-------------|-------------|------|
| VPS-WORKINGLOCAL | systemd service | amd64 | 100.107.226.24 | — |
| NETWORKSERVER | systemd service | amd64 | 100.119.137.54 | coretemp ~54°C |
| MEDIASERVER | systemd service | amd64 | 100.111.62.69 | coretemp ~43°C |
| AI-NODE-I9 | systemd service | amd64 | 100.126.121.11 | coretemp ~53°C |
| AI-NODE-I5 | systemd service | amd64 | 100.78.175.49 | coretemp ~36°C |
| TRAVELSERVER | Docker app (TrueNAS) | amd64 | 100.83.16.76 | coretemp ~52°C |
| NUT-SERVER Pi | systemd service | armv7 | 100.97.195.23 | thermal_zone ~54°C |
| VM-AutoBA | Docker container (host network) | amd64 | 100.107.82.21 | — |
| VM-AI-Engine | systemd service | amd64 | 100.80.180.55 | — |
| VM-ADGUARD | systemd service | amd64 | 100.121.177.76 | — |
| VM-PLEX | systemd service | amd64 | 100.83.181.85 | — |
| VM-IMMICH | systemd service | amd64 | 100.75.33.124 | — |
| VM-APPS | systemd service | amd64 | 100.97.124.46 | — |
| HAOS-NUC | Netdata add-on | amd64 | 100.109.230.93 | — |
| WINDOWSSERVER2025 | windows_exporter MSI :9182 | amd64 | 100.92.201.100 | WMI geen data |
