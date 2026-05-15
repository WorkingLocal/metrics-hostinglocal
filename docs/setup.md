# Setup handleiding — Metrics Stack

## Stack overzicht

| Container | Rol | Netwerk |
|-----------|-----|---------|
| `prometheus-metrics` | Metrics scrapen van alle nodes | `host` (voor Tailscale toegang) |
| `grafana-metrics` | Dashboards | `monitoring` + Traefik netwerk |
| `alertmanager-metrics` | E-mail alerts | `monitoring` |
| `uptime-kuma-metrics` | URL/port uptime | `monitoring` + Traefik netwerk |

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
        └── dashboards/
            ├── dashboards.yml
            ├── temperatures.json
            ├── ai-nodes.json
            └── adguard-home.json
```

## Credentials

| Service | Gebruiker | Wachtwoord |
|---------|-----------|-----------|
| Grafana | admin | zie `.env` op VPS |
| Uptime Kuma | admin | zelfde als Grafana |
| Prometheus | — | geen auth (intern) |
| Alertmanager | — | geen auth (intern) |

## Eerste installatie

### 1. Bestanden deployen

```bash
# Vanuit de metrics-hostinglocal repo:
bash deploy.sh --smtp-password <hostinger-wachtwoord>
```

### 2. .env aanmaken op VPS

```bash
ssh root@23.94.220.181
cat > /data/coolify/services/metrics-stack/.env << EOF
GRAFANA_ADMIN_PASSWORD=<sterk-wachtwoord>
SMTP_PASSWORD=<hostinger-smtp-wachtwoord>
EOF
```

### 3. Stack starten

```bash
cd /data/coolify/services/metrics-stack
docker compose up -d
```

### 4. node_exporter op VPS installeren

```bash
# Als root op VPS:
bash install-node-exporter.sh
```

### 5. Grafana dashboards importeren

Provisioned dashboards (temperatures.json, ai-nodes.json, adguard-home.json) verschijnen automatisch.

Geïmporteerde dashboards via Grafana UI (Dashboards → Import → ID invoeren):
- **Node Exporter Full** (ID 1860) — Linux node metrics
- **Windows Exporter Dashboard** (ID 14694) — Windows Server metrics

## node_exporter op Linux nodes installeren

```bash
# SSH naar de node en uitvoeren als root:
bash install-node-exporter.sh
```

Installeert node_exporter met temperatuurcollectors:
- `--collector.hwmon` — hardware monitor temperaturen (coretemp, nvme, etc.)
- `--collector.thermal_zone` — ACPI thermal zones
- `--collector.textfile.directory=/var/lib/node_exporter/textfile_collector` — custom metrics

Getest op: Ubuntu, Debian, Raspberry Pi OS (auto-detectie van arch: amd64/arm64/armv7).

## lm-sensors installeren

lm-sensors zorgt dat node_exporter de sensornamen correct weergeeft (bijv. "Package id 0" i.p.v. "temp1"):

```bash
bash install-lm-sensors.sh
```

Geïnstalleerd op: AI-NODE-I9, AI-NODE-I5, NETWORKSERVER, MEDIASERVER, NUT-SERVER.

## Intel GPU temperatuur collector

Intel iGPU temperatuur via textfile collector (alleen als i915/xe hwmon beschikbaar is):

```bash
# Deployen naar een AI node:
bash scripts/deploy-intel-gpu-temp.sh <tailscale-ip>
```

**Let op:** Op de huidige hosts (AI-NODE-I9, AI-NODE-I5, MEDIASERVER) is i915/xe hwmon NIET beschikbaar. De GPU temperatuur is niet beschikbaar in Prometheus.

## windows_exporter op Windows Server

1. Download MSI van https://github.com/prometheus-community/windows_exporter/releases
2. Installeer: `msiexec /i windows_exporter-*.msi /quiet ENABLED_COLLECTORS=cpu,cs,logical_disk,net,os,service,system,memory,thermalzone`
3. Default luistert op poort 9182

Thermalzone collector inschakelen op bestaande installatie (PowerShell als Administrator):
```powershell
# windows-temp/setup.ps1 uitvoeren op WINDOWSSERVER2025
```

**Let op:** WMI thermalzone geeft geen data terug op Windows Server 2025 als Hyper-V host.

## Nieuwe node toevoegen

1. Installeer node_exporter: `bash install-node-exporter.sh`
2. Installeer lm-sensors: `bash install-lm-sensors.sh`
3. Voeg toe aan `prometheus.yml`:
   ```yaml
   - job_name: 'nieuwe-node'
     static_configs:
       - targets: ['<tailscale-ip>:9100']
         labels:
           instance: 'NIEUWE-NODE'
   ```
4. Deploy en herlaad:
   ```bash
   bash deploy-config.sh
   ssh root@23.94.220.181 'curl -s -X POST http://localhost:9090/-/reload'
   ```
5. Voeg node toe aan `temperatures.json` stat-panel en tijdreeks-query.

## Prometheus targets verifiëren

```bash
ssh root@23.94.220.181
curl -s http://localhost:9090/api/v1/targets | python3 -c "
import json,sys
d=json.load(sys.stdin)
for t in d['data']['activeTargets']:
    print(t['health'], t['labels']['job'], t['labels']['instance'])
"
```

## DNS vereisten

| Record | Waarde |
|--------|--------|
| metrics.hostinglocal.be | A → 23.94.220.181 (Cloudflare proxy AAN) |
| uptime.hostinglocal.be | A → 23.94.220.181 (Cloudflare proxy AAN) |

## Cloudflare instellingen

- SSL/TLS mode: **Full** (niet Flexible, niet Strict)
- **Always Use HTTPS**: Ingeschakeld (vervangt Traefik redirect-to-https middleware)
- Geen Page Rules of Redirect Rules nodig
