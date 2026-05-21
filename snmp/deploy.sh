#!/bin/bash
# Deploy SNMP Exporter naar NETWORKSERVER (100.119.137.54) als systemd binary
# Gebruik: bash snmp/deploy.sh
# Uitvoeren vanuit de root van de repo

set -e

GREEN='\033[0;32m'
NC='\033[0m'
log() { echo -e "${GREEN}✓${NC} $1"; }

NETWORKSERVER_IP="100.119.137.54"
SCRIPT="snmp/install-snmp-exporter.sh"

echo "=== SNMP Exporter deployen naar ${NETWORKSERVER_IP} ==="

# Check of snmp_exporter al draait
if ssh root@"$NETWORKSERVER_IP" "systemctl is-active snmp_exporter" &>/dev/null; then
  log "snmp_exporter draait al op ${NETWORKSERVER_IP} — installatie overgeslagen"
else
  scp "$SCRIPT" root@"$NETWORKSERVER_IP":/tmp/install-snmp-exporter.sh
  log "install script gekopieerd"
  ssh root@"$NETWORKSERVER_IP" "bash /tmp/install-snmp-exporter.sh"
  log "installatie voltooid"
fi

echo ""
echo "=== Test ==="
RESULT=$(ssh root@"$NETWORKSERVER_IP" \
  "curl -sf 'http://localhost:9116/snmp?target=192.168.111.1&module=if_mib' | head -5" 2>&1) || true

if echo "$RESULT" | grep -q "^#"; then
  log "SNMP scrape succesvol — Unifi Gateway antwoordt"
  echo "$RESULT"
else
  echo "⚠ SNMP scrape geeft geen data — SNMP ingeschakeld op Unifi?"
  echo "  Unifi UI → Settings → System → Traffic & Services → SNMP Monitoring v1/2c"
  echo "  Dan opnieuw testen: curl 'http://${NETWORKSERVER_IP}:9116/snmp?target=192.168.111.1&module=if_mib'"
fi
