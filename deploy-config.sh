#!/bin/bash
# Deploy metrics stack configuratie naar VPS
# Gebruik: bash deploy-config.sh [--smtp-password <wachtwoord>]

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
log()  { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }

VPS_IP="23.94.220.181"
DEPLOY_DIR="/data/coolify/services/metrics-stack"
SMTP_PASSWORD="${2}"

echo "=== Metrics stack config deployen naar ${VPS_IP} ==="

# Prometheus en alerting config
for f in prometheus.yml alert.rules.yml alertmanager.yml; do
    scp "$f" root@"$VPS_IP":"${DEPLOY_DIR}/${f}"
    log "$f gekopieerd"
done

# Grafana provisioning
scp grafana/provisioning/datasources/prometheus.yml root@"$VPS_IP":"${DEPLOY_DIR}/grafana/provisioning/datasources/prometheus.yml"
scp grafana/provisioning/dashboards/dashboards.yml root@"$VPS_IP":"${DEPLOY_DIR}/grafana/provisioning/dashboards/dashboards.yml"
scp grafana/provisioning/dashboards/temperatures.json root@"$VPS_IP":"${DEPLOY_DIR}/grafana/provisioning/dashboards/temperatures.json"
scp grafana/provisioning/dashboards/adguard-home.json root@"$VPS_IP":"${DEPLOY_DIR}/grafana/provisioning/dashboards/adguard-home.json"
scp grafana/provisioning/dashboards/ai-nodes.json root@"$VPS_IP":"${DEPLOY_DIR}/grafana/provisioning/dashboards/ai-nodes.json"
log "Grafana provisioning gekopieerd"

# SMTP wachtwoord instellen
if [[ -n "$SMTP_PASSWORD" ]]; then
    ssh root@"$VPS_IP" "sed -i 's/VERVANG_MET_SMTP_WACHTWOORD/${SMTP_PASSWORD}/g' ${DEPLOY_DIR}/alertmanager.yml"
    ssh root@"$VPS_IP" "sed -i 's/SMTP_PASSWORD=.*/SMTP_PASSWORD=${SMTP_PASSWORD}/' ${DEPLOY_DIR}/.env"
    log "SMTP wachtwoord ingesteld"
    # Alertmanager herstarten om nieuw wachtwoord te laden
    ssh root@"$VPS_IP" "cd ${DEPLOY_DIR} && docker compose restart alertmanager grafana"
    log "Alertmanager en Grafana herstart"
else
    warn "Geen SMTP wachtwoord opgegeven"
    warn "Stel in via: bash deploy-config.sh --smtp-password <wachtwoord>"
fi

log "Config deploy klaar."
