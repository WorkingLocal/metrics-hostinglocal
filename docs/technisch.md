# Technische documentatie — Metrics Stack

## Architectuur

```
Internet
    │
    └── Cloudflare
         ├── ntfy.hostinglocal.be    → 172.245.52.210 (VPS-HOSTINGLOCAL)
         ├── uptime.hostinglocal.be  → 172.245.52.210 (VPS-HOSTINGLOCAL)
         └── metrics.hostinglocal.be → 192.168.111.18 (METRICSSERVER, DNS pending)

VPS-HOSTINGLOCAL (172.245.52.210 / Tailscale 100.125.153.71)
    └── Docker Compose /opt/vps-hostinglocal/
         ├── caddy :80/:443         — TLS terminatie + reverse proxy
         ├── ntfy :2586             — Push notificaties (topic: homelab)
         └── uptime-kuma :3001      — Uptime monitoring

METRICSSERVER (192.168.111.18 / Tailscale 100.67.19.40)
    ├── prometheus-metrics :9090   — host network, scrapet alle nodes via Tailscale
    ├── smartctl-exporter :9633    — host network, SMART disk health lokale NVMe
    ├── Docker bridge (proxy network)
    │    ├── grafana-metrics        — dashboards (via host.docker.internal:9090)
    │    └── alertmanager-metrics :9093
    └── Docker bridge (metrics_internal network)
         ├── alertmanager-metrics   — ontvangt alerts van Prometheus
         ├── alertmanager-ntfy      — Flask bridge → stuurt naar ntfy VPS-HOSTINGLOCAL
         └── thermal-shutdown       — SSH graceful shutdown bij thermische alerts

Tailscale nodes (geschraped door Prometheus via Tailscale mesh)
    ├── localhost:9100             — METRICSSERVER (node_exporter systemd)
    ├── 100.125.153.71:9100        — VPS-HOSTINGLOCAL (node_exporter systemd)
    ├── 100.92.201.100:9182        — WINDOWSSERVER2025 (windows_exporter)
    ├── 100.119.137.54:9100        — NETWORKSERVER
    ├── 100.111.62.69:9100         — MEDIASERVER
    ├── 100.126.121.11:9100        — AI-NODE-I9
    ├── 100.78.175.49:9100         — AI-NODE-I5
    ├── 100.83.16.76:9100          — TRAVELSERVER (TrueNAS SCALE)
    ├── 100.97.195.23:9100         — NUT-SERVER Pi (armv7)
    ├── 100.107.82.21:9100         — VM-AutoBA
    ├── 100.80.180.55:9100         — VM-AI-Engine
    ├── 100.121.177.76:9100+9617   — VM-ADGUARD (node_exporter + adguard-home exporter)
    ├── 100.75.230.22:9100         — VM-NPM
    ├── 100.122.166.117:9100       — VM-NETBOX
    ├── 100.83.181.85:9100         — VM-PLEX
    ├── 100.75.33.124:9100         — VM-IMMICH
    ├── 100.97.124.46:9100         — VM-APPS
    ├── 100.92.71.9:9100           — VM-OPENCLAW
    ├── 100.72.50.41:9100          — FILESERVER (node_exporter Docker)
    └── 192.168.111.1 (via snmp-exporter 100.119.137.54:9116) — UNIFI-GATEWAY

HAOS-NUC (192.168.111.75:8123)
    └── Native HA Prometheus endpoint /api/prometheus
         — bearer token auth, scrape_interval 120s
         — METRICSSERVER bereikt HAOS via lokaal netwerk (geen Tailscale)
```

## Docker Compose netwerken (METRICSSERVER)

| Container | Netwerken | Reden |
|-----------|-----------|-------|
| prometheus-metrics | host | Tailscale IPs bereiken |
| smartctl-exporter | host | Directe toegang tot /dev/sd*, /dev/nvme* |
| grafana-metrics | proxy | Bereikbaar voor reverse proxy, Prometheus via host.docker.internal |
| alertmanager-metrics | proxy + metrics_internal | Extern bereikbaar (9093), intern communicatie |
| alertmanager-ntfy | proxy + metrics_internal | Ontvangt webhooks van alertmanager via intern netwerk |
| thermal-shutdown | metrics_internal | Ontvangt webhooks van alertmanager, voert SSH uit |

**Belangrijk:** Grafana gebruikt `extra_hosts: host.docker.internal:host-gateway` om Prometheus op `localhost:9090` te bereiken zonder host network mode.

## Prometheus configuratie

- Config bestand: `/opt/metrics-hostinglocal/prometheus.yml` (geüpload vanuit `prometheus.hostinglocal.yml`)
- Scrape interval: 15s globaal
- Speciale intervals: `haos-nuc` 120s, `unifi-snmp` 60s
- Data retentie: 30 dagen
- Hot reload: `POST http://192.168.111.18:9090/-/reload`
- Flag: `--web.enable-lifecycle` (hot reload actief)

## Alertmanager configuratie

- Config: `/opt/metrics-hostinglocal/alertmanager.yml`
- Routing: warning → ntfy only, critical → ntfy + email
- Geen hot reload — vereist `docker restart alertmanager-metrics`
- Grouping: per `[alertname, instance]`

## alertmanager-ntfy bridge

Custom Flask container die Alertmanager webhooks ontvangt en doorstuurt naar ntfy.

Omgevingsvariabelen:
```
NTFY_URL=http://100.125.153.71:2586
NTFY_TOPIC=homelab
NTFY_TOKEN=<publisher token>
```

De URL verwijst direct naar de ntfy poort op VPS-HOSTINGLOCAL via Tailscale — geen DNS nodig.

## thermal-shutdown

Python SSH-client die reageert op Alertmanager webhooks met label `thermal=true`.
Voert `shutdown -h +1` (of host-specifiek commando) uit via SSH met de `thermal_shutdown` sleutel.

SSH private key: `/root/.ssh/thermal_shutdown` op METRICSSERVER  
Gemount in container: `/root/.ssh/thermal_shutdown:/app/keys/id_ed25519:ro`  
Hosts config: `thermal-shutdown/hosts.yml`

## Grafana

- Image: `grafana/grafana:11.6.2` — vastgepind, nooit `latest` (Grafana 13 had 307 loop bug + schema-incompatibiliteit met 11.x data)
- Volume: `metrics_grafana_data`
- Datasource: Prometheus via `http://host.docker.internal:9090`
- Dashboard provisioning: `/etc/grafana/provisioning/dashboards/` (bind mount)
- SMTP: via `GF_SMTP_*` env vars
- Root URL: `https://metrics.hostinglocal.be`

### Grafana volume reset procedure

Als het Grafana volume gereset moet worden (bv. na schema conflict):
```bash
docker compose -f compose.hostinglocal.yml stop grafana-metrics
docker rm grafana-metrics
docker volume rm metrics_grafana_data
docker compose -f compose.hostinglocal.yml up -d grafana-metrics
```
Provisioned dashboards verschijnen automatisch na herstart.

## HAOS Energie-monitoring

### Prometheus metric namen (namespace: homeassistant)

| Metric | Entiteit | Eenheid |
|--------|----------|---------|
| `homeassistant_sensor_power_w` | beem + ups | W |
| `homeassistant_sensor_energy_wh` | beem daily/monthly | Wh |
| `homeassistant_sensor_energy_kwh` | beem totaal + homelab totaal | kWh |
| `homeassistant_sensor_battery_percent` | ups battery charge | % |
| `homeassistant_sensor_unit_percent` | ups load | % |
| `homeassistant_sensor_duration_s` | ups runtime | s |
| `homeassistant_sensor_voltage_v` | ups input voltage | V |
| `homeassistant_sensor_apparent_power_va` | ups apparent power | VA |
| `homeassistant_sensor_signal_strength_dbm` | beem invertor wifi | dBm |

Entiteiten worden gefilterd via de `entity` label in PromQL:
```promql
homeassistant_sensor_power_w{entity="sensor.beem_energy_thomas_vandromme_current_power"}
```

## SMART disk health

`smartctl-exporter` draait in host network mode, exposes NVMe SMART metrics op `:9633`.
Job: `smartctl-metricsserver`, instance: `METRICSSERVER`.

Voorbeeld query — reallocated sectors:
```promql
smartctl_device_attribute{instance="METRICSSERVER", attribute_name="Reallocated_Sector_Ct"}
```

## Temperatuurmonitoring

### node_exporter flags

Alle Linux nodes hebben node_exporter met:
```
--collector.hwmon
--collector.thermal_zone
--collector.textfile.directory=/var/lib/node_exporter/textfile_collector
```

### Temperatuur per host

| Host | Metric | Chip |
|------|--------|------|
| AI-NODE-I9/I5, NETWORKSERVER, MEDIASERVER | `node_hwmon_temp_celsius{chip="platform_coretemp_0",sensor="temp1"}` | coretemp |
| NUT-SERVER Pi | `node_hwmon_temp_celsius{chip="thermal_thermal_zone0"}` | thermal_zone |
| WINDOWSSERVER2025 | `windows_thermalzone_temperature_kelvin - 273.15` | WMI (geen data op Hyper-V) |

## node_exporter installaties per node

| Node | Methode | Arch | Tailscale IP |
|------|---------|------|-------------|
| METRICSSERVER | systemd service | amd64 | localhost |
| VPS-HOSTINGLOCAL | systemd service | amd64 | 100.125.153.71 |
| NETWORKSERVER | systemd service | amd64 | 100.119.137.54 |
| MEDIASERVER | systemd service | amd64 | 100.111.62.69 |
| AI-NODE-I9 | systemd service | amd64 | 100.126.121.11 |
| AI-NODE-I5 | systemd service | amd64 | 100.78.175.49 |
| TRAVELSERVER | Docker app (TrueNAS) | amd64 | 100.83.16.76 |
| NUT-SERVER Pi | systemd service | armv7 | 100.97.195.23 |
| VM-AutoBA | Docker host network | amd64 | 100.107.82.21 |
| VM-AI-Engine | systemd service | amd64 | 100.80.180.55 |
| VM-ADGUARD | systemd service | amd64 | 100.121.177.76 |
| VM-PLEX | systemd service | amd64 | 100.83.181.85 |
| VM-IMMICH | systemd service | amd64 | 100.75.33.124 |
| VM-APPS | systemd service | amd64 | 100.97.124.46 |
| VM-NPM | systemd service | amd64 | 100.75.230.22 |
| VM-NETBOX | systemd service | amd64 | 100.122.166.117 |
| VM-OPENCLAW | systemd service | amd64 | 100.92.71.9 |
| FILESERVER | Docker host network | amd64 | 100.72.50.41 |
| WINDOWSSERVER2025 | windows_exporter MSI :9182 | amd64 | 100.92.201.100 |

## Bestanden op METRICSSERVER

```
/opt/metrics-hostinglocal/
├── compose.hostinglocal.yml
├── prometheus.yml              ← prometheus.hostinglocal.yml uit repo
├── alert.rules.yml
├── alertmanager.yml
├── .env                        ← GRAFANA_ADMIN_PASSWORD + SMTP_PASSWORD + NTFY_*
├── alertmanager-ntfy/
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
├── thermal-shutdown/
│   ├── Dockerfile
│   ├── app.py
│   ├── hosts.yml
│   └── requirements.txt
├── snmp/
└── grafana/
    └── provisioning/
        ├── datasources/prometheus.yml
        └── dashboards/
            ├── dashboards.yml
            └── *.json          ← alle Grafana dashboards
```

## Credentials

| Service | Gebruiker | Locatie |
|---------|-----------|---------|
| METRICSSERVER SSH | `metrics` / `KtO9r6zioQ0agXfnP73N` | Vaultwarden → Homelab - Infrastructure |
| Grafana | `admin` / zie .env | Vaultwarden → Homelab - Infrastructure |
| ntfy admin | `thomas` | Vaultwarden → Homelab - Infrastructure |
| ntfy publisher token | `tk_okm65mem9fj8by2w2w48uoz14j630` | Vaultwarden → "ntfy — publisher token homelab" |
| HAOS Bearer token | — | Vaultwarden → Home Assistant |
