#!/bin/bash
# Deploy SNMP Exporter naar NETWORKSERVER (100.119.137.54)
# Gebruik: bash snmp/deploy.sh

set -e

GREEN='\033[0;32m'
NC='\033[0m'
log() { echo -e "${GREEN}✓${NC} $1"; }

NETWORKSERVER_IP="100.119.137.54"
DEPLOY_DIR="/opt/snmp-exporter"

echo "=== SNMP Exporter deployen naar ${NETWORKSERVER_IP} ==="

ssh root@"$NETWORKSERVER_IP" "mkdir -p ${DEPLOY_DIR}"

scp snmp/docker-compose.yml root@"$NETWORKSERVER_IP":"${DEPLOY_DIR}/docker-compose.yml"
log "docker-compose.yml gekopieerd"

ssh root@"$NETWORKSERVER_IP" "cd ${DEPLOY_DIR} && docker compose up -d"
log "SNMP Exporter gestart op poort 9116"

echo ""
echo "Test: curl 'http://${NETWORKSERVER_IP}:9116/snmp?target=192.168.111.1&module=if_mib'"
