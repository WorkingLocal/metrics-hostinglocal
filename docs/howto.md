# Hoe gebruik ik de monitoring stack?

## Dashboards bekijken

**Grafana:** https://metrics.hostinglocal.be
- Login: `admin` / zie `.env` op VPS
- Beschikbare dashboards:
  - **Node Exporter Full** — gedetailleerde Linux metrics per node
  - **Windows Exporter** — Windows Server 2025 metrics
  - **AI Nodes Load Monitor** — CPU/RAM/Netwerk/Disk/Temps voor AI-NODE-I9 + I5
  - **Host Temperatures** — CPU-temperaturen alle fysieke hosts

**Uptime Kuma:** https://uptime.hostinglocal.be
- Login: `admin` / zelfde wachtwoord als Grafana
- Publieke status page: https://uptime.hostinglocal.be/status/hosting-local

---

## E-mailmeldingen

Alerts komen van `info@workinglocal.be` naar `thomas@workinglocal.be`.

**Subject formaat:**
- `[WARNING] HighCpuUsage — VM-AUTOBA`
- `[CRITICAL] InstanceDown — NUT-SERVER`

Warnings herhalen elke **12 uur** zolang het probleem aanhoudt.
Criticals herhalen elke **1 uur**.

---

## node_exporter installeren op een nieuwe Linux node

```bash
# SSH naar de node als root:
bash install-node-exporter.sh
```

Daarna toevoegen in `prometheus.yml`:

```yaml
- job_name: 'nieuwe-node'
  static_configs:
    - targets: ['<tailscale-ip>:9100']
      labels:
        instance: 'NIEUWE-NODE'
```

Deploy en herlaad:

```bash
bash deploy-config.sh
ssh root@23.94.220.181 'curl -s -X POST http://localhost:9090/-/reload'
```

---

## windows_exporter installeren op Windows

1. Download MSI: https://github.com/prometheus-community/windows_exporter/releases
2. Installeer: `msiexec /i windows_exporter-*.msi /quiet ENABLED_COLLECTORS=cpu,cs,logical_disk,net,os,service,system,memory,thermalzone`
3. Poort 9182, bereikbaar via Tailscale
4. Voeg toe aan `prometheus.yml` met poort 9182

---

## Grafana dashboards importeren na volume-reset

Als het Grafana volume gereset is (na downgrade of herstel), moeten Node Exporter Full en Windows Exporter opnieuw geïmporteerd worden. Provisioned dashboards (temperatures, ai-nodes, adguard-home) verschijnen automatisch.

```bash
# Haal datasource UID op:
ssh root@23.94.220.181
GRAFANA_PASS=$(grep GRAFANA_ADMIN_PASSWORD /data/coolify/services/metrics-stack/.env | cut -d= -f2)
DS_UID=$(curl -s -u admin:$GRAFANA_PASS http://localhost:3000/api/datasources | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['uid'])")

# Importeer via API (vervang DS_UID):
cat > /tmp/import.py << 'EOF'
import requests, json
base = "http://localhost:3000"
auth = ("admin", "GRAFANA_PASS_HIER")
ds_uid = "DS_UID_HIER"

for gf_id in [1860, 14694]:
    dash = requests.get(f"https://grafana.com/api/dashboards/{gf_id}/revisions/latest/download").json()
    for panel in dash.get("panels", []) + [p for row in dash.get("panels",[]) if row.get("panels") for p in row["panels"]]:
        for t in panel.get("targets", []):
            if "datasource" in t:
                t["datasource"] = {"type": "prometheus", "uid": ds_uid}
    payload = {"dashboard": dash, "overwrite": True, "inputs": [{"name": "DS_PROMETHEUS", "type": "datasource", "pluginId": "prometheus", "value": ds_uid}]}
    r = requests.post(f"{base}/api/dashboards/import", json=payload, auth=auth)
    print(gf_id, r.status_code, r.json().get("status",""))
EOF
python3 /tmp/import.py
```

---

## Drempelwaarden aanpassen

Bewerk `alert.rules.yml` in de repo en deploy:

```bash
scp alert.rules.yml root@23.94.220.181:/data/coolify/services/metrics-stack/
ssh root@23.94.220.181 'curl -s -X POST http://localhost:9090/-/reload'
```

Zie [alerts.md](alerts.md) voor een overzicht van alle regels.

---

## Alertmanager routing aanpassen

Bewerk `alertmanager.yml` en herstart:

```bash
scp alertmanager.yml root@23.94.220.181:/data/coolify/services/metrics-stack/
ssh root@23.94.220.181 'docker restart alertmanager-metrics'
```

Of gebruik het deploy script:

```bash
bash deploy-config.sh --smtp-password <wachtwoord>
```

---

## Temperaturen bekijken

Open het **Host Temperatures** dashboard in Grafana. Toont:
- CPU Package-temperatuur van alle fysieke hosts (stat-panels + tijdreeks)
- GPU-temperatuur (Intel iGPU — momenteel geen data, i915 hwmon niet beschikbaar)

Temperatuur per host opvragen via Prometheus:
```bash
ssh root@23.94.220.181
curl -s 'http://localhost:9090/api/v1/query?query=max+by+%28instance%29+%28node_hwmon_temp_celsius%7Bchip%3D~%22coretemp.*%22%2Csensor%3D%22temp1%22%7D%29'
```

---

## Problemen oplossen

| Probleem | Oplossing |
|----------|-----------|
| Host staat op "down" in Prometheus | `curl http://<tailscale-ip>:9100/metrics` — draait node_exporter? |
| Geen e-mailmeldingen | `docker logs alertmanager-metrics` — SMTP fout? |
| Grafana 504 fout | Uptime Kuma mag niet de publieke URL gebruiken (hairpin NAT) — gebruik `http://grafana-metrics:3000/api/health` |
| Prometheus regels niet geladen | `curl -s http://localhost:9090/api/v1/rules` op VPS |
| Grafana redirect loop (ERR_TOO_MANY_REDIRECTS) | Verwijder redirect-to-https middleware uit Traefik labels. Gebruik Cloudflare "Always Use HTTPS". Controleer of Grafana image niet `latest` is (pin op 11.6.2). |
| Grafana N/A na downgrade | Grafana 13→11 schema-incompatibiliteit: volume resetten (zie howto hierboven) |
| Geen temperatuurdata | Controleer node_exporter flags: `--collector.hwmon` en `--collector.thermal_zone` aanwezig? |
