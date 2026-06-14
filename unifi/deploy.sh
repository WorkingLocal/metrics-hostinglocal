#!/bin/bash
# Deploy UniFi monitoring naar METRICSSERVER
# Gebruik: bash unifi/deploy.sh
# Uitvoeren vanuit de root van de repo

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
log()  { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }

METRICSSERVER_IP="192.168.111.18"
REMOTE_DIR="/opt/metrics-hostinglocal"

echo "=== UniFi monitoring deployen naar ${METRICSSERVER_IP} ==="
echo ""

# Vereiste .env variabelen checken
if ! ssh root@"$METRICSSERVER_IP" "grep -q 'UNIFI_POLLER_USER=.' ${REMOTE_DIR}/.env 2>/dev/null"; then
  warn "UNIFI_POLLER_USER niet ingevuld in .env op METRICSSERVER"
  warn "Sla eerst credentials op in Vaultwarden en vul .env in:"
  echo "  ssh root@${METRICSSERVER_IP}"
  echo "  nano ${REMOTE_DIR}/.env"
  echo "  # Voeg toe: UNIFI_POLLER_USER=... en UNIFI_POLLER_PASS=..."
  echo ""
fi

# Bestanden synchroniseren
rsync -av --exclude='.git' --exclude='.env' \
  alertmanager-ntfy/ \
  root@"$METRICSSERVER_IP":"${REMOTE_DIR}/alertmanager-ntfy/"
log "alertmanager-ntfy bestanden gesynchroniseerd"

rsync -av \
  compose.hostinglocal.yml \
  prometheus.hostinglocal.yml \
  alert.rules.yml \
  alertmanager.yml \
  root@"$METRICSSERVER_IP":"${REMOTE_DIR}/"
log "compose + config bestanden gesynchroniseerd"

# Containers herstarten
ssh root@"$METRICSSERVER_IP" bash << EOF
  cd ${REMOTE_DIR}

  # alertmanager-ntfy herbouwen (nieuwe /unifi-hook endpoint)
  docker compose -f compose.hostinglocal.yml build alertmanager-ntfy
  docker compose -f compose.hostinglocal.yml up -d alertmanager-ntfy

  # unifi-poller starten (nieuw)
  docker compose -f compose.hostinglocal.yml up -d unifi-poller

  # Prometheus herladen (nieuwe scrape config + alert rules)
  docker compose -f compose.hostinglocal.yml up -d prometheus
  sleep 3
  curl -sf -X POST http://localhost:9090/-/reload && echo "✓ Prometheus config herladen"
EOF

log "Deploy voltooid"
echo ""
echo "=== Controleer ==="
echo "  unifi-poller logs:     ssh root@${METRICSSERVER_IP} 'docker logs unifi-poller --tail 20'"
echo "  Prometheus targets:    http://metrics.hostinglocal.be/targets (zoek naar unifi-poller)"
echo "  Test webhook:          curl -X POST http://${METRICSSERVER_IP}:9095/unifi-hook -H 'Content-Type: application/json' \\"
echo "                           -d '{\"key\":\"EVT_AP_Lost_Contact\",\"data\":{\"ap_name\":\"Test AP\",\"msg\":\"Test event\"}}'"
echo ""
echo "=== Option A: UniFi webhook instellen ==="
echo "  UniFi UI → Settings → System → Notifications → Add Webhook"
echo "  URL: http://${METRICSSERVER_IP}:9095/unifi-hook"
