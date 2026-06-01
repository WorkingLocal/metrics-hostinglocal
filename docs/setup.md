# Setup handleiding — Metrics Stack

## Architectuur overzicht

De metrics stack bestaat uit twee onderdelen:

1. **METRICSSERVER** (192.168.111.18) — Prometheus + Grafana + Alertmanager + thermal-shutdown
2. **VPS-HOSTINGLOCAL** (100.125.153.71 / 172.245.52.210) — ntfy + Uptime Kuma + Caddy

---

## METRICSSERVER setup

### Hardware

| Component | Waarde |
|-----------|--------|
| Model | Dell OptiPlex 3050 SFF |
| CPU | Intel i5-7500 |
| RAM | 16GB DDR4 |
| Opslag | 256GB NVMe |
| OS | Ubuntu (bare metal) |
| Lokaal IP | 192.168.111.18 |
| Tailscale IP | 100.67.19.40 |
| SSH user | `metrics` |

### Stack locatie op server

```
/opt/metrics-hostinglocal/
├── compose.hostinglocal.yml
├── prometheus.yml          ← geüpload vanuit prometheus.hostinglocal.yml
├── alert.rules.yml
├── alertmanager.yml
├── .env
├── alertmanager-ntfy/
├── thermal-shutdown/
├── snmp/
└── grafana/
    └── provisioning/
        ├── datasources/
        └── dashboards/
```

### .env op METRICSSERVER

```
GRAFANA_ADMIN_PASSWORD=<zie Vaultwarden>
SMTP_PASSWORD=<Hostinger SMTP>
NTFY_PUBLISHER_TOKEN=<zie Vaultwarden → ntfy token>
NTFY_URL=http://100.125.153.71:2586
```

### Deploy (Windows)

Gebruik het Python deploy script:

```
C:\Temp\deploy_sftp.py
```

Dit script:
- Verbindt via paramiko SSH/SFTP naar 192.168.111.18
- Uploadt alle bestanden (inclusief `prometheus.hostinglocal.yml` → `prometheus.yml`)
- Maakt `.env` aan
- Maakt Docker netwerken `proxy` en `metrics_internal` aan
- Start de stack met `docker compose -f compose.hostinglocal.yml up -d`

```bash
python C:\Temp\deploy_sftp.py
```

### Alleen config bijwerken (zonder volledige deploy)

1. Bestand lokaal aanpassen in de repo
2. Via SFTP uploaden:
   ```python
   sftp.put("prometheus.hostinglocal.yml", "/opt/metrics-hostinglocal/prometheus.yml")
   ```
3. Prometheus hot-reload:
   ```bash
   curl -s -X POST http://192.168.111.18:9090/-/reload
   ```

### Docker netwerken

| Netwerk | Type | Doel |
|---------|------|------|
| `host` | host | Prometheus bereikt Tailscale nodes |
| `proxy` | external bridge | Grafana + Alertmanager bereikbaar voor reverse proxy |
| `metrics_internal` | intern | Interne communicatie Alertmanager ↔ alertmanager-ntfy ↔ thermal-shutdown |

`proxy` network aanmaken (eenmalig):
```bash
docker network create proxy
```

### Grafana toegang

Grafana is niet direct op een poort gekoppeld — alleen via het `proxy` Docker netwerk.
Tijdelijke directe toegang via de container IP:
```bash
docker inspect grafana-metrics | grep IPAddress
# → http://<container-ip>:3000
```

Externe toegang via reverse proxy: `metrics.hostinglocal.be` (Cloudflare → METRICSSERVER, DNS pending).

### Prometheus targets verifiëren

```bash
curl -s http://192.168.111.18:9090/api/v1/targets | python3 -c "
import json,sys
d=json.load(sys.stdin)
for t in d['data']['activeTargets']:
    print(t['health'], t['labels']['job'], t['labels'].get('instance',''))
"
```

### Nieuwe node toevoegen

1. Installeer node_exporter op de node: `bash install-node-exporter.sh`
2. Voeg toe aan `prometheus.hostinglocal.yml`:
   ```yaml
   - job_name: 'nieuwe-node'
     static_configs:
       - targets: ['<tailscale-ip>:9100']
         labels:
           instance: 'NIEUWE-NODE'
   ```
3. Upload en hot-reload:
   ```python
   sftp.put("prometheus.hostinglocal.yml", "/opt/metrics-hostinglocal/prometheus.yml")
   # daarna:
   curl -s -X POST http://192.168.111.18:9090/-/reload
   ```
4. Voeg toe aan het temperatures-dashboard als fysieke host.

---

## VPS-HOSTINGLOCAL setup

### Server info

| Component | Waarde |
|-----------|--------|
| Provider | Linode |
| Publiek IP | 172.245.52.210 |
| Tailscale IP | 100.125.153.71 |
| OS | Ubuntu (heropgezet mei 2026) |
| Stack locatie | `/opt/vps-hostinglocal/` |

### Geïnstalleerde services

- **Docker** (handmatig geïnstalleerd)
- **Tailscale** (handmatig geïnstalleerd, gekoppeld aan tailnet)
- **node_exporter** (systemd service op poort 9100)
- **ntfy + Uptime Kuma + Caddy** (Docker Compose stack)

### Stack locatie

```
/opt/vps-hostinglocal/
├── compose.yml         # ntfy + uptime-kuma + caddy
├── Caddyfile           # ntfy.hostinglocal.be + uptime.hostinglocal.be
└── (ntfy auth/cache DB → Docker volumes)
```

### compose.yml (VPS-HOSTINGLOCAL)

```yaml
services:
  ntfy:
    image: binwiederhier/ntfy:latest
    command: serve
    environment:
      - NTFY_BASE_URL=https://ntfy.hostinglocal.be
      - NTFY_AUTH_DEFAULT_ACCESS=deny-all
      - NTFY_BEHIND_PROXY=true
    volumes:
      - ntfy_data:/var/lib/ntfy
    ports:
      - "2586:80"

  uptime-kuma:
    image: louislam/uptime-kuma:1
    volumes:
      - uptime_kuma_data:/app/data
    ports:
      - "127.0.0.1:3001:3001"

  caddy:
    image: caddy:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
```

### Caddyfile

```
ntfy.hostinglocal.be {
    reverse_proxy ntfy:80
}
uptime.hostinglocal.be {
    reverse_proxy uptime-kuma:3001
}
```

### ntfy user & token

- Admin user: `thomas`
- Topic: `homelab`
- Publisher token: zie Vaultwarden → Homelab - Infrastructure → "ntfy — publisher token homelab"

### DNS (Cloudflare — pending)

| Record | Type | Waarde |
|--------|------|--------|
| ntfy.hostinglocal.be | A | 172.245.52.210 |
| uptime.hostinglocal.be | A | 172.245.52.210 |

---

## HAOS Prometheus integratie

HAOS exporteert alle numerieke entiteiten naar `/api/prometheus` (native HA integratie).

`configuration.yaml` op HAOS (192.168.111.75):
```yaml
prometheus:
  namespace: homeassistant
```

Prometheus job in `prometheus.hostinglocal.yml`:
```yaml
- job_name: 'haos-nuc'
  scrape_interval: 120s
  metrics_path: /api/prometheus
  bearer_token: '<long-lived token — zie Vaultwarden → Home Assistant>'
  static_configs:
    - targets: ['192.168.111.75:8123']
      labels:
        instance: 'HAOS-NUC'
```

METRICSSERVER bereikt HAOS via lokaal netwerk (geen Tailscale nodig).

---

## node_exporter installeren op Linux node

```bash
# SSH naar de node als root:
bash install-node-exporter.sh
```

Installeert node_exporter met:
- `--collector.hwmon` — hardware temperaturen
- `--collector.thermal_zone` — ACPI thermal zones
- `--collector.textfile.directory` — custom metrics

Auto-detectie van architectuur: amd64 / arm64 / armv7.

## lm-sensors installeren

```bash
bash install-lm-sensors.sh
```

Geïnstalleerd op: AI-NODE-I9, AI-NODE-I5, NETWORKSERVER, MEDIASERVER, NUT-SERVER.

## windows_exporter op Windows Server

Download en installeer de MSI:
```
msiexec /i windows_exporter-*.msi /quiet ENABLED_COLLECTORS=cpu,cs,logical_disk,net,os,service,system,memory,thermalzone
```
Luistert standaard op poort 9182.

## Thermal shutdown SSH key distribueren

Publieke sleutel (van `/root/.ssh/thermal_shutdown.pub` op METRICSSERVER):
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAr/tovxf6AYTHL4hxe7vT/zcGgly/BKKP0laOE1Odhj thermal-shutdown@metricsserver
```

Op elke node toevoegen:
```bash
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAr/tovxf6AYTHL4hxe7vT/zcGgly/BKKP0laOE1Odhj thermal-shutdown@metricsserver" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Status (juni 2026): gedistribueerd naar AI-NODE-I9 ✅, AI-NODE-I5 ✅, NETWORKSERVER ✅, MEDIASERVER ✅, NUT-SERVER ✅, HAOS-NUC ✅, WINDOWSSERVER2025 ✅, FILESERVER ⏳, TRAVELSERVER ⏳

---

## PBS relay installeren op METRICSSERVER

METRICSSERVER fungeert als TCP relay voor externe servers (VPS) naar PBS op het lokale netwerk.

```bash
sudo apt-get install -y socat

# Service bestand staat in infra-hostinglocal/compose/pbs-backup/pbs-relay.service
sudo cp pbs-relay.service /etc/systemd/system/pbs-relay.service
sudo systemctl daemon-reload
sudo systemctl enable pbs-relay
sudo systemctl start pbs-relay
sudo systemctl status pbs-relay
```

De relay bindt uitsluitend op de Tailscale interface (100.67.19.40:8007) en stuurt door naar
PBS op het lokale netwerk (192.168.111.201:8007).

---

## Deploy script (Windows → METRICSSERVER)

`deploy_sftp.py` staat in de repo root. Gebruik het om de volledige stack te deployen:

```bash
python deploy_sftp.py
```

Vereiste: `pip install paramiko`
SSH credentials: Vaultwarden → Homelab - Infrastructure → METRICSSERVER SSH

Het script:
- Verbindt via paramiko SFTP naar 192.168.111.18
- Uploadt compose file, prometheus config, alertmanager config, dashboards, thermal-shutdown, alertmanager-ntfy
- Maakt Docker netwerken `proxy` en `metrics_internal` aan
- Start de stack met `docker compose -f compose.hostinglocal.yml up -d`

---

## Grafana dashboards overzicht (juni 2026)

| Dashboard | UID | Bestand |
|---|---|---|
| Homelab Overview | homelab-overview-hl | overview.json |
| AI Nodes Load Monitor | 2ca2c5e5-... | ai-nodes.json |
| Host Temperatures | host-temperatures-hl | temperatures.json |
| Energie & Zonnepanelen | energie-zonnepanelen | energie.json |
| Personal Health | personal-health-hl | personal.json |
| Disk Overview | disk-overview-hl | disk-overview.json |
| AdGuard Home DNS | adguard-home-hostinglocal | adguard-home.json |
| Unifi Gateway | unifi-gateway-hl | unifi.json |
| Windows Server 2025 | windows-server-hl | windows-server.json |
| HAOS NUC | haos-nuc-hl | haos.json |
| FILESERVER DS423+ | fileserver-hl | fileserver.json |
| NETWORKSERVER | networkserver-hl | networkserver.json |
| VPS | vps-hl | vps.json |
| Controllers | controllers-hl | controllers.json |
| Backup Monitoring | backup-monitoring-hl | backup-monitoring.json |
| NetBox | netbox-hl | netbox.json |
