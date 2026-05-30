# Operationele handleiding — Metrics Stack

## Grafana openen

- Extern: https://metrics.hostinglocal.be (DNS pending → tijdelijk via container IP)
- Login: `admin` / zie Vaultwarden → Homelab - Infrastructure → "METRICSSERVER — Grafana"

---

## Prometheus targets controleren

```bash
curl -s http://192.168.111.18:9090/api/v1/targets | python3 -c "
import json,sys
d=json.load(sys.stdin)
for t in d['data']['activeTargets']:
    print(t['health'], t['labels']['job'], t['labels'].get('instance',''))
"
```

Of via Prometheus UI: http://192.168.111.18:9090/targets

---

## Prometheus config bijwerken (hot reload)

```bash
# 1. Wijzig prometheus.hostinglocal.yml lokaal
# 2. Upload naar METRICSSERVER
python C:\Temp\deploy_sftp.py
# OF handmatig via SFTP:
#   sftp.put("prometheus.hostinglocal.yml", "/opt/metrics-hostinglocal/prometheus.yml")
# 3. Hot reload (geen herstart nodig):
curl -s -X POST http://192.168.111.18:9090/-/reload
```

---

## Alertmanager herstarten (na config-wijziging)

Alertmanager ondersteunt geen hot reload:
```bash
ssh metrics@192.168.111.18
echo 'metrics' | sudo -S docker restart alertmanager-metrics
```

---

## ntfy notificaties

Push-notificaties komen op het `homelab` topic via `https://ntfy.hostinglocal.be`.

Handmatig bericht sturen (test):
```bash
curl -X POST https://ntfy.hostinglocal.be/homelab \
  -H "Authorization: Bearer tk_okm65mem9fj8by2w2w48uoz14j630" \
  -d "Test notificatie van METRICSSERVER"
```

Zie `docs/ntfy-integrations.md` voor integraties met Uptime Kuma, HAOS, FILESERVER en UniFi.

---

## Grafana dashboard toevoegen

1. Maak of download een dashboard JSON
2. Sla op in `grafana/provisioning/dashboards/<naam>.json`
3. Upload naar METRICSSERVER:
   ```bash
   python C:\Temp\deploy_sftp.py
   # of handmatig:
   # sftp.put("grafana/provisioning/dashboards/naam.json",
   #          "/opt/metrics-hostinglocal/grafana/provisioning/dashboards/naam.json")
   ```
4. Herstart Grafana:
   ```bash
   ssh metrics@192.168.111.18
   echo '<pw>' | sudo -S docker restart grafana-metrics
   ```

---

## Grafana volume resetten (noodprocedure)

Nodig bij schema-incompatibiliteit (bv. na image upgrade):
```bash
ssh metrics@192.168.111.18
cd /opt/metrics-hostinglocal
echo '<pw>' | sudo -S bash -c "
  docker compose -f compose.hostinglocal.yml stop grafana-metrics
  docker rm grafana-metrics
  docker volume rm metrics_grafana_data
  docker compose -f compose.hostinglocal.yml up -d grafana-metrics
"
```
Provisioned dashboards (alle `*.json` in provisioning) verschijnen automatisch.

---

## Stack herstarten (volledig)

```bash
ssh metrics@192.168.111.18
cd /opt/metrics-hostinglocal
echo '<pw>' | sudo -S docker compose -f compose.hostinglocal.yml restart
```

Of selectief:
```bash
# Alleen Grafana
echo '<pw>' | sudo -S docker restart grafana-metrics
# Alleen Alertmanager
echo '<pw>' | sudo -S docker restart alertmanager-metrics
```

---

## Stack updaten (nieuwe images)

```bash
ssh metrics@192.168.111.18
cd /opt/metrics-hostinglocal
echo '<pw>' | sudo -S bash -c "
  docker compose -f compose.hostinglocal.yml pull
  docker compose -f compose.hostinglocal.yml up -d
"
```

**Let op:** Grafana is vastgepind op `11.6.2` in de compose — `pull` zal het niet upgraden.

---

## Container logs bekijken

```bash
ssh metrics@192.168.111.18
echo '<pw>' | sudo -S docker logs grafana-metrics --tail 50
echo '<pw>' | sudo -S docker logs prometheus-metrics --tail 50
echo '<pw>' | sudo -S docker logs alertmanager-metrics --tail 50
echo '<pw>' | sudo -S docker logs alertmanager-ntfy --tail 50
echo '<pw>' | sudo -S docker logs thermal-shutdown-metrics --tail 50
```

---

## VPS-HOSTINGLOCAL stack beheren

```bash
ssh root@100.125.153.71
cd /opt/vps-hostinglocal
docker compose logs ntfy --tail 30
docker compose logs uptime-kuma --tail 30
docker compose restart
```

---

## Drempelwaarden aanpassen

Bewerk `alert.rules.yml` en deploy + reload:
```bash
python C:\Temp\deploy_sftp.py
curl -s -X POST http://192.168.111.18:9090/-/reload
```

---

## Temperaturen bekijken

Open het **Host Temperatures** dashboard in Grafana, of via Prometheus:
```bash
curl -s 'http://192.168.111.18:9090/api/v1/query?query=max+by(instance)(node_hwmon_temp_celsius%7Bchip%3D~"coretemp.*"%2Csensor%3D"temp1"%7D)'
```

---

## Problemen oplossen

| Probleem | Oplossing |
|----------|-----------|
| Host staat "down" in Prometheus | `curl http://<tailscale-ip>:9100/metrics` — draait node_exporter? |
| Geen ntfy notificaties | `docker logs alertmanager-ntfy` — NTFY_URL correct? Token geldig? |
| Geen e-mailmeldingen | `docker logs alertmanager-metrics` — SMTP configuratie correct in alertmanager.yml? |
| Grafana niet bereikbaar | Container in proxy network? `docker inspect grafana-metrics` → IP, dan `curl http://<ip>:3000` |
| Prometheus regels niet geladen | `curl -s http://192.168.111.18:9090/api/v1/rules` |
| Grafana redirect loop (ERR_TOO_MANY_REDIRECTS) | Cloudflare Redirect Rules controleren. Grafana image = 11.6.2 (niet latest). |
| HAOS target down | Bearer token vervallen? Controleer via `curl -H "Authorization: Bearer <token>" http://192.168.111.75:8123/api/prometheus` |
| Geen temperatuurdata op node | node_exporter flags controleren: `--collector.hwmon` + `--collector.thermal_zone` aanwezig? |
| thermal-shutdown verbindt niet | SSH key `thermal_shutdown.pub` toegevoegd aan `~/.ssh/authorized_keys` op doelnode? |
