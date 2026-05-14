#!/bin/bash
# Deploy metrics stack naar VPS-WORKINGLOCAL
# Gebruik: bash deploy.sh [--smtp-password <wachtwoord>]

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
log()  { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }

VPS_IP="23.94.220.181"
DEPLOY_DIR="/data/coolify/services/metrics-stack"
SMTP_PASSWORD="${2}"

echo "=== Metrics stack deployen naar ${VPS_IP} ==="

# Map aanmaken op VPS
ssh root@"$VPS_IP" "mkdir -p ${DEPLOY_DIR}/grafana/provisioning/datasources ${DEPLOY_DIR}/grafana/provisioning/dashboards"

# Config bestanden kopiëren
for f in docker-compose.yml prometheus.yml alert.rules.yml alertmanager.yml; do
    scp "$f" root@"$VPS_IP":"${DEPLOY_DIR}/${f}"
    log "$f gekopieerd"
done

scp grafana/provisioning/datasources/prometheus.yml root@"$VPS_IP":"${DEPLOY_DIR}/grafana/provisioning/datasources/prometheus.yml"
scp grafana/provisioning/dashboards/dashboards.yml root@"$VPS_IP":"${DEPLOY_DIR}/grafana/provisioning/dashboards/dashboards.yml"
scp grafana/provisioning/dashboards/temperatures.json root@"$VPS_IP":"${DEPLOY_DIR}/grafana/provisioning/dashboards/temperatures.json"
scp grafana/provisioning/dashboards/ai-nodes.json root@"$VPS_IP":"${DEPLOY_DIR}/grafana/provisioning/dashboards/ai-nodes.json"
scp grafana/provisioning/dashboards/adguard-home.json root@"$VPS_IP":"${DEPLOY_DIR}/grafana/provisioning/dashboards/adguard-home.json"
log "Grafana provisioning gekopieerd"

# SMTP wachtwoord invullen in alertmanager.yml
if [[ -n "$SMTP_PASSWORD" ]]; then
    ssh root@"$VPS_IP" "sed -i 's/VERVANG_MET_SMTP_WACHTWOORD/${SMTP_PASSWORD}/' ${DEPLOY_DIR}/alertmanager.yml"
    log "SMTP wachtwoord ingesteld"
else
    warn "Geen SMTP wachtwoord opgegeven — alertmanager kan geen e-mails versturen"
    warn "Stel in via: bash deploy.sh --smtp-password <wachtwoord>"
fi

log "Deploy klaar. Gebruik 'bash deploy.sh --smtp-password <wachtwoord>' om notificaties te activeren."
warn "SNMP Exporter (Unifi) apart deployen: bash snmp/deploy.sh"
