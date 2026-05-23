#!/bin/bash
# Deploy metrics stack naar VPS-HOSTINGLOCAL
# Gebruik: bash deploy-hostinglocal.sh [--smtp-password <wachtwoord>]

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
log()  { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }

VPS_IP="172.245.52.210"
VPS_PW="XK3fnm6Eo4O58B2Rjx"
HOSTKEY="ssh-ed25519 255 AAAAC3NzaC1lZDI1NTE5AAAAIBBg50/XarGn8FKj6mOt9lA3L5nEr0JoaInOL0NmLGvD"
DEPLOY_DIR="/root/compose/metrics"
SMTP_PASSWORD="${2}"

PLINK="plink -ssh -pw '${VPS_PW}' -batch -hostkey '${HOSTKEY}' root@${VPS_IP}"
PSCP="pscp -pw '${VPS_PW}' -batch -hostkey '${HOSTKEY}'"

echo "=== Metrics stack deployen naar VPS-HOSTINGLOCAL (${VPS_IP}) ==="

# Directories aanmaken
plink -ssh -pw "${VPS_PW}" -batch -hostkey "${HOSTKEY}" root@${VPS_IP} \
  "mkdir -p ${DEPLOY_DIR}/grafana/provisioning/datasources ${DEPLOY_DIR}/grafana/provisioning/dashboards"
log "Directories aangemaakt"

# Config bestanden kopiëren
for f in compose.hostinglocal.yml prometheus.hostinglocal.yml alertmanager.yml alert.rules.yml; do
  pscp -pw "${VPS_PW}" -batch -hostkey "${HOSTKEY}" "$f" root@${VPS_IP}:${DEPLOY_DIR}/
  log "$f gekopieerd"
done

# Rename op server
plink -ssh -pw "${VPS_PW}" -batch -hostkey "${HOSTKEY}" root@${VPS_IP} \
  "cd ${DEPLOY_DIR} && mv -f compose.hostinglocal.yml compose.yml; mv -f prometheus.hostinglocal.yml prometheus.yml"
log "Bestanden hernoemd"

# Grafana provisioning
pscp -pw "${VPS_PW}" -batch -hostkey "${HOSTKEY}" \
  grafana/provisioning/datasources/prometheus.yml \
  root@${VPS_IP}:${DEPLOY_DIR}/grafana/provisioning/datasources/
pscp -pw "${VPS_PW}" -batch -hostkey "${HOSTKEY}" \
  grafana/provisioning/dashboards/dashboards.yml \
  root@${VPS_IP}:${DEPLOY_DIR}/grafana/provisioning/dashboards/
log "Grafana provisioning config gekopieerd"

# Dashboard JSONs
for json in grafana/provisioning/dashboards/*.json; do
  pscp -pw "${VPS_PW}" -batch -hostkey "${HOSTKEY}" "$json" root@${VPS_IP}:${DEPLOY_DIR}/grafana/provisioning/dashboards/
done
log "Dashboard JSONs gekopieerd"

# .env aanmaken
GRAFANA_PW="${GRAFANA_ADMIN_PASSWORD:-yUVostImZ9ULlDW}"
plink -ssh -pw "${VPS_PW}" -batch -hostkey "${HOSTKEY}" root@${VPS_IP} \
  "echo -e 'GRAFANA_ADMIN_PASSWORD=${GRAFANA_PW}\nSMTP_PASSWORD=${SMTP_PASSWORD}' > ${DEPLOY_DIR}/.env"
log ".env aangemaakt"

# Stack starten
plink -ssh -pw "${VPS_PW}" -batch -hostkey "${HOSTKEY}" root@${VPS_IP} \
  "cd ${DEPLOY_DIR} && docker compose up -d"
log "Stack gestart"

echo ""
log "Deploy klaar!"
echo "  Grafana: https://metrics.hostinglocal.be (admin / ${GRAFANA_PW})"
echo "  Prometheus: http://${VPS_IP}:9090 (intern)"
if [[ -z "$SMTP_PASSWORD" ]]; then
  warn "Geen SMTP wachtwoord — stel in via: bash deploy-hostinglocal.sh --smtp-password <ww>"
fi
