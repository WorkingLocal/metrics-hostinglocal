# ntfy integraties — Homelab

ntfy server: `https://ntfy.hostinglocal.be` (na DNS update)  
Topic: `homelab`  
Publisher token: zie Vaultwarden → "VPS-HOSTINGLOCAL — ntfy"  
Admin: `thomas` / zie Vaultwarden

## Alertmanager → ntfy ✅ (automatisch via bridge)

Geconfigureerd via `alertmanager-ntfy` bridge container.  
Warnings → ntfy only. Critical → ntfy + email.

---

## Uptime Kuma → ntfy

**Stappen (UI, eenmalig):**

1. Open Uptime Kuma → Settings → Notifications → Add Notification
2. Notification Type: **ntfy**
3. Server URL: `http://ntfy:80` (intern Docker netwerk)
4. Topic: `homelab`
5. Token: `tk_y53hf22ahj046z85mod20uixysue3`
6. Priority: **High** (4) voor down, **Low** (2) voor recovered
7. Sla op → koppel aan alle monitors

---

## Home Assistant → ntfy

Voeg toe aan `configuration.yaml`:

```yaml
notify:
  - name: ntfy_homelab
    platform: rest
    resource: http://ntfy.hostinglocal.be/homelab
    method: POST_JSON
    headers:
      Authorization: Bearer tk_y53hf22ahj046z85mod20uixysue3
    title_param_name: title
    message_param_name: message
```

Gebruik in automations:
```yaml
action:
  - service: notify.ntfy_homelab
    data:
      title: "🏠 HA Alert"
      message: "{{ trigger.description }}"
```

Of via de officiële [ntfy HACS integratie](https://github.com/ivanstepachev/ha_ntfy):

1. HACS → Integrations → zoek "ntfy"
2. Server URL: `https://ntfy.hostinglocal.be`
3. Token: `tk_y53hf22ahj046z85mod20uixysue3`
4. Topic: `homelab`

---

## UniFi → ntfy

UniFi heeft geen native ntfy support maar ondersteunt webhooks:

1. UniFi Console → Settings → Notifications → Webhooks
2. Add Webhook:
   - URL: `https://ntfy.hostinglocal.be/homelab`
   - Method: POST
   - Header `Authorization`: `Bearer tk_y53hf22ahj046z85mod20uixysue3`
   - Header `Content-Type`: `text/plain`
3. Body: laat leeg → ntfy toont de ruwe UniFi JSON als bericht

---

## Synology DSM (FILESERVER) → ntfy

### Optie A: DSM Webhooks (DSM 7.2+)

1. Control Panel → Notification → SMS tab → Toevoegen
2. SMS provider: **Custom**
3. Provider naam: `ntfy`
4. URL: `https://ntfy.hostinglocal.be/homelab`
5. HTTP Method: POST
6. HTTP Header:
   ```
   Authorization: Bearer tk_y53hf22ahj046z85mod20uixysue3
   Content-Type: application/json
   ```
7. Body:
   ```json
   {"message":"%%SYNO_MESSAGE%%","title":"FILESERVER: %%SYNO_CATEGORY%%","priority":3}
   ```

### Optie B: Script via Task Scheduler (betrouwbaarder)

Upload `/usr/local/bin/ntfy-notify.sh` naar FILESERVER via SSH:

```bash
#!/bin/bash
# Stuur bericht naar ntfy homelab topic
# Gebruik: ntfy-notify.sh "Titel" "Bericht" [prioriteit]
TITLE="${1:-FILESERVER}"
MSG="${2:-Geen bericht}"
PRIO="${3:-3}"
NTFY_TOKEN="tk_y53hf22ahj046z85mod20uixysue3"
NTFY_URL="https://ntfy.hostinglocal.be/homelab"

curl -s -X POST "$NTFY_URL" \
  -H "Authorization: Bearer $NTFY_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"$MSG\",\"title\":\"$PRIO\",\"priority\":$PRIO}"
```

Installeer:
```bash
# SSH naar FILESERVER (poort 221)
ssh -p 221 vandrommethomas@100.72.50.41

# Script plaatsen
sudo bash -c 'cat > /usr/local/bin/ntfy-notify.sh' << 'SCRIPT'
# (zie inhoud hierboven)
SCRIPT
sudo chmod +x /usr/local/bin/ntfy-notify.sh

# Test
ntfy-notify.sh "FILESERVER Test" "Script werkt!" 3
```

DSM Task Scheduler → Triggered Task → koppel aan DSM events (backup voltooid, schijffout, etc.):
- Script: `/usr/local/bin/ntfy-notify.sh "FILESERVER Backup" "HyperBackup voltooid" 2`

---

## Credential overzicht

| Gebruik | Waarde |
|---------|--------|
| Server URL (intern) | `http://ntfy:80` |
| Server URL (extern, na DNS) | `https://ntfy.hostinglocal.be` |
| Topic | `homelab` |
| Publisher token | `tk_y53hf22ahj046z85mod20uixysue3` |
| Admin login | `thomas` / zie Vaultwarden |
