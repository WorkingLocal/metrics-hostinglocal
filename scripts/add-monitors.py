"""
Voeg ontbrekende Uptime Kuma monitors toe voor alle Homelab services.

Gebruik:
  pip install uptime-kuma-api
  python scripts/add-monitors.py

De script checkt eerst welke monitors al bestaan (op naam) en slaat die over.
Notification ID 1 wordt aan alle nieuwe monitors gekoppeld.

Manuele stap NA dit script:
  Uptime Kuma UI → Notifications → Edit "ntfy" → Topic wijzigen van "homelab" naar "hl-uptime"
"""

from uptime_kuma_api import UptimeKumaApi, MonitorType

UPTIME_KUMA_URL  = "http://100.103.226.56:3001"
UPTIME_KUMA_USER = "admin"
UPTIME_KUMA_PASS = "Homelab2026!"
NOTIFICATION_ID  = 1  # ntfy notificatie (ID 1 in Uptime Kuma)

# Alle nieuwe monitors: (naam, type, url_of_hostname, poort_of_None, extra_kwargs)
# extra_kwargs: dict met MonitorType-specifieke opties
NEW_MONITORS = [

    # ── INFRASTRUCTUUR ────────────────────────────────────────────────────────

    # Proxmox hosts (zelf-getekend TLS)
    ("Proxmox PDM",          MonitorType.HTTPS, "https://100.86.178.45:8006",   None, {"ignoreTls": True, "interval": 120}),
    ("Proxmox PVE-MS01-i9",  MonitorType.HTTPS, "https://100.81.170.58:8006",  None, {"ignoreTls": True, "interval": 120}),
    ("Proxmox PVE-MS01-i5",  MonitorType.HTTPS, "https://100.94.188.94:8006",  None, {"ignoreTls": True, "interval": 120}),

    # AI nodes (Ollama draait in VM)
    ("VM-AI-NODE-I9 Ollama",    MonitorType.HTTP,  "http://100.64.1.25:11434",     None, {"interval": 60}),
    ("VM-AI-NODE-I5 Ollama",    MonitorType.HTTP,  "http://100.101.48.4:11434",    None, {"interval": 60}),

    # Netwerk & toegang
    ("AdGuard Home",         MonitorType.HTTP,  "http://100.121.177.76:3000",   None, {"interval": 60}),
    ("NPM (Nginx Proxy Mgr)",MonitorType.HTTP,  "http://100.75.230.22:81",      None, {"interval": 60}),

    # AI gateway / tooling
    ("AI Engine (LiteLLM)",  MonitorType.HTTP,  "http://100.80.180.55:4000/health", None, {"interval": 60}),
    ("OpenClaw Gateway",     MonitorType.HTTP,  "http://100.92.71.9:18789/healthz", None, {"interval": 60}),

    # Monitoring
    ("Alertmanager",         MonitorType.HTTP,  "http://100.67.19.40:9093/-/healthy", None, {"interval": 120}),

    # Backup server
    ("TrueNAS TRAVELSERVER", MonitorType.HTTPS, "https://100.83.29.41",         None, {"ignoreTls": True, "interval": 120}),

    # Power management
    ("Power Control FANSERVER", MonitorType.HTTP, "http://100.103.226.56:8765/health", None, {"interval": 120}),
    ("Power Control NUT-SERVER", MonitorType.HTTP, "http://100.97.195.23:8765/health", None, {"interval": 120}),

    # ── MEDIA ─────────────────────────────────────────────────────────────────

    ("Tautulli",             MonitorType.HTTP,  "http://100.83.181.85:8181",    None, {"interval": 120}),
    ("Lidarr",               MonitorType.HTTP,  "http://100.77.174.124:8686",   None, {"interval": 120}),
    ("MusicAssistant",       MonitorType.HTTP,  "http://100.77.174.124:8095",   None, {"interval": 120}),
    ("Bonob SMAPI",          MonitorType.HTTP,  "http://100.77.174.124:4534",   None, {"interval": 120}),
    ("BookStack",            MonitorType.HTTP,  "http://100.107.238.37:6875",   None, {"interval": 120}),
    ("Calibre Web",          MonitorType.HTTP,  "http://100.107.238.37:8083",   None, {"interval": 120}),

    # ── WORKINGLOCAL / AUTOBA ─────────────────────────────────────────────────

    ("Xibo CMS",             MonitorType.HTTPS, "https://signage.workinglocal.be",  None, {"interval": 120}),
    ("WordPress WorkingLocal",MonitorType.HTTPS,"https://workinglocal.be",      None, {"interval": 120}),
    ("Coolify WorkingLocal", MonitorType.HTTPS, "https://coolify.workinglocal.be",  None, {"interval": 120}),
    ("Metrics WorkingLocal", MonitorType.HTTPS, "https://metrics.workinglocal.be",  None, {"interval": 120}),
    ("Focus App",            MonitorType.HTTPS, "https://focus.workinglocal.be",    None, {"interval": 120}),
    ("Photoframe",           MonitorType.HTTPS, "https://frame.workinglocal.be",    None, {"interval": 120}),

    # AutoBA platform (via Cloudflare tunnel)
    ("AutoBA Platform",      MonitorType.HTTPS, "https://autoba.hostinglocal.be",   None, {"interval": 60}),
    ("BMS Portal",           MonitorType.HTTPS, "https://bms.thinkinglocal.be",     None, {"interval": 60}),
    ("AutoBA Plane",         MonitorType.HTTPS, "https://autoba-plane.hostinglocal.be", None, {"interval": 120}),
    ("AutoBA Gitea",         MonitorType.HTTPS, "https://autoba.hostinglocal.be/gitea/", None, {"interval": 120}),
    ("AutoBA n8n",           MonitorType.HTTPS, "https://autoba.hostinglocal.be/n8n/",  None, {"interval": 120}),
    ("AutoBA Metabase",      MonitorType.HTTPS, "https://autoba.hostinglocal.be/metabase/", None, {"interval": 120}),

    # ── PERSOONLIJK ───────────────────────────────────────────────────────────

    ("Personal Portal",      MonitorType.HTTP,  "http://100.92.201.100:8500",   None, {"interval": 120}),

    # ── TCP PORT CHECKS ───────────────────────────────────────────────────────

    ("AI-ENGINE SSH",        MonitorType.TCP_PORT, "100.80.180.55",  22,   {"interval": 120}),
    ("VM-AUTOBA SSH",        MonitorType.TCP_PORT, "100.107.82.21",  22,   {"interval": 120}),
    ("VM-OPENCLAW SSH",      MonitorType.TCP_PORT, "100.92.71.9",    22,   {"interval": 120}),
    ("NETWORKSERVER SSH",    MonitorType.TCP_PORT, "100.119.137.54", 22,   {"interval": 120}),
    ("MEDIASERVER SSH",      MonitorType.TCP_PORT, "100.111.62.69",  22,   {"interval": 120}),
    ("WINDOWSSERVER SSH",    MonitorType.TCP_PORT, "100.92.201.100", 22,   {"interval": 120}),
]


def main():
    print(f"Verbinden met Uptime Kuma op {UPTIME_KUMA_URL} ...")
    with UptimeKumaApi(UPTIME_KUMA_URL) as api:
        api.login(UPTIME_KUMA_USER, UPTIME_KUMA_PASS)
        print("✅ Ingelogd.\n")

        # Bestaande monitors ophalen (op naam) om duplicaten te vermijden
        existing = api.get_monitors()
        existing_names = {m["name"].lower() for m in existing}
        print(f"Bestaande monitors: {len(existing_names)} stuks")

        added = 0
        skipped = 0

        for entry in NEW_MONITORS:
            name, mon_type, url_or_host, port, kwargs = entry

            if name.lower() in existing_names:
                print(f"  ⏭  Overgeslagen (bestaat al): {name}")
                skipped += 1
                continue

            try:
                params = {
                    "type":               mon_type,
                    "name":               name,
                    "notificationIDList": {str(NOTIFICATION_ID): True},
                    **kwargs,
                }

                if mon_type == MonitorType.TCP_PORT:
                    params["hostname"] = url_or_host
                    params["port"]     = port
                else:
                    params["url"] = url_or_host

                api.add_monitor(**params)
                print(f"  ✅ Toegevoegd: {name}")
                added += 1

            except Exception as exc:
                print(f"  ❌ FOUT bij {name}: {exc}")

        print(f"\nKlaar — {added} toegevoegd, {skipped} overgeslagen.")
        print("\n⚠️  MANUELE STAP:")
        print("   Uptime Kuma UI → Settings → Notifications → Edit 'ntfy'")
        print("   → Topic wijzigen van 'homelab' naar 'hl-uptime'")
        print("   → Klik op 'Test' om te verifiëren, dan 'Save'.")


if __name__ == "__main__":
    main()
