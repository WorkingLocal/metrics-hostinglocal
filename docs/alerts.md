# Alert regels — Metrics Stack

Alerts worden gedefinieerd in `alert.rules.yml` en verwerkt door Prometheus + Alertmanager.

## Prometheus alert regels

| Alert | Expressie | Drempel | Duur | Ernst |
|-------|-----------|---------|------|-------|
| `InstanceDown` | `up == 0` | host niet bereikbaar | 2 min | critical |
| `HighCpuUsage` | CPU idle berekening | >80% | 5 min | warning |
| `HighMemoryUsage` | RAM beschikbaar vs totaal | >80% | 5 min | warning |
| `NvmeDiskUsageHigh` | `/dev/nvme*` gebruik | >80% | 5 min | warning |
| `NvmeDiskUsageCritical` | `/dev/nvme*` gebruik | >90% | 1 min | critical |
| `HighTemperatureWarning` | `node_hwmon_temp_celsius` (coretemp/thermal_zone) | >80°C | 30s | warning, `action: cooldown` |
| `HighTemperatureCritical` | `node_hwmon_temp_celsius` (coretemp/thermal_zone) | >90°C | 30s | critical, `action: shutdown` |

**NVMe filter:** disk alerts enkel op `/dev/nvme*` devices — geen Docker overlay, tmpfs of virtuele partities.

## Thermische actie-routing (cooldown/shutdown, 2026-07-11)

Naast de gewone ntfy-notificaties triggeren de twee temperatuur-alerts een echte actie via
de `thermal-shutdown` container (poort 9095), die enkel een **dispatcher** is naar de
[power-control](../../infra-hostinglocal/power-control/) API (FANSERVER primair, NUT-SERVER
backup) — die kent de graceful VM/LXC-evacuatie per host, thermal-shutdown zelf doet geen SSH meer.

```
action: cooldown (80°C) → thermal-shutdown:9095/cooldown → power-control /api/cooldown/{host}
                                                              (CPU powersave+no_turbo, niet-destructief)
action: shutdown (90°C) → thermal-shutdown:9095/webhook  → power-control /api/shutdown/{host}
                                                              (graceful, evacueert VM's/LXC's eerst)
```

Instance→power-control-hostname mapping staat in `thermal-shutdown/hosts.yml`
(`instance_map`). Instances zonder mapping (bv. FANSERVER zelf) worden genegeerd —
geen crash, gewoon een genegeerde actie + log-regel.

Dedup: shutdown-acties herhalen ten vroegste na 1u per host, cooldown-acties na 10 min
(niet-destructief, mag vaker), cooldown-reset (bij `resolved`) na 30s.

## Alertmanager routing

```
Alle alerts
├── severity=critical → email-critical
│     group_wait: 30s | group_interval: 5m | repeat: 1h
└── severity=warning  → email-warning (default)
      group_wait: 2m  | group_interval: 10m | repeat: 12h
```

Grouping: `[alertname, instance]` → één mail per host per alerttype.

**Inhibit rule:** als een critical actief is op een host, worden warnings voor diezelfde host onderdrukt.

## Mail subject formaat

| Ernst | Subject |
|-------|---------|
| Warning | `[WARNING] HighCpuUsage — VM-AUTOBA` |
| Critical | `[CRITICAL] InstanceDown — NUT-SERVER` |
| Resolved | zelfde subject, body vermeldt "RESOLVED" |

## SMTP configuratie

| Instelling | Waarde |
|-----------|--------|
| Server | smtp.hostinger.com:587 (STARTTLS) |
| Afzender | info@workinglocal.be |
| Ontvanger | thomas@workinglocal.be |
| Wachtwoord | in `.env` op VPS (`SMTP_PASSWORD`) |

## Drempelwaarden aanpassen

Bewerk `alert.rules.yml` en deploy:

```bash
bash deploy-config.sh --smtp-password <wachtwoord>
```

Prometheus herlaadt regels via `POST /-/reload` (geen herstart nodig).
Alertmanager vereist wel een herstart: `docker restart alertmanager-metrics`.
