#!/bin/bash
# Installeer lm-sensors op een Linux bare-metal host
# node_exporter pikt daarna automatisch CPU/case temp op via node_hwmon_temp_celsius
# Gebruik: bash install-lm-sensors.sh

set -e

GREEN='\033[0;32m'
NC='\033[0m'
log() { echo -e "${GREEN}✓${NC} $1"; }

echo "=== lm-sensors installeren ==="

apt-get update -q
apt-get install -y lm-sensors

# Auto-detect alle sensor chips (antwoordt 'yes' op alle vragen)
yes | sensors-detect --auto 2>/dev/null || true

# Kernel modules laden voor gevonden chips
service kmod start 2>/dev/null || modprobe $(sensors-detect --auto 2>/dev/null | grep "^modprobe" | awk '{print $2}') 2>/dev/null || true

log "lm-sensors geïnstalleerd"
echo ""
echo "--- Huidige sensorwaarden ---"
sensors
echo ""
echo "--- node_exporter hwmon metrics ---"
curl -s http://localhost:9100/metrics 2>/dev/null | grep "^node_hwmon_temp_celsius" | head -20 || echo "  (node_exporter niet bereikbaar op :9100)"
echo ""
log "Klaar — node_exporter verzamelt temperaturen via node_hwmon_temp_celsius"
log "  Herstart node_exporter als metrics leeg zijn: systemctl restart node_exporter"
