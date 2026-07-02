#!/bin/bash
# Deploy Intel GPU temp collector naar een AI node (i9 of i5 MS-01)
# Gebruik: bash scripts/deploy-intel-gpu-temp.sh <tailscale-ip>
# Voorbeeld: bash scripts/deploy-intel-gpu-temp.sh 100.81.170.58   (PVE-MS01-I9)
#            bash scripts/deploy-intel-gpu-temp.sh 100.94.188.94    (PVE-MS01-I5)

set -e

GREEN='\033[0;32m'
NC='\033[0m'
log() { echo -e "${GREEN}✓${NC} $1"; }

HOST="${1}"
if [[ -z "$HOST" ]]; then
    echo "Gebruik: bash scripts/deploy-intel-gpu-temp.sh <tailscale-ip>"
    echo "  PVE-MS01-I9: 100.81.170.58"
    echo "  PVE-MS01-I5: 100.94.188.94"
    exit 1
fi

echo "=== Intel GPU temp collector deployen naar ${HOST} ==="

# Script kopiëren
scp scripts/intel-gpu-temp-collector.sh root@"${HOST}":/usr/local/bin/intel-gpu-temp-collector.sh
ssh root@"${HOST}" "chmod +x /usr/local/bin/intel-gpu-temp-collector.sh"
log "Collector script gekopieerd"

# Textfile directory aanmaken (als node_exporter al draait, bestaat die al)
ssh root@"${HOST}" "mkdir -p /var/lib/node_exporter/textfile_collector && chown nobody:nogroup /var/lib/node_exporter/textfile_collector"
log "Textfile directory aangemaakt"

# Systemd timer installeren (elke minuut)
ssh root@"${HOST}" "cat > /etc/systemd/system/intel-gpu-temp.service << 'EOF'
[Unit]
Description=Intel GPU temp textfile collector

[Service]
Type=oneshot
ExecStart=/usr/local/bin/intel-gpu-temp-collector.sh
EOF"

ssh root@"${HOST}" "cat > /etc/systemd/system/intel-gpu-temp.timer << 'EOF'
[Unit]
Description=Intel GPU temp collector — elke minuut

[Timer]
OnBootSec=30s
OnUnitActiveSec=1min
Unit=intel-gpu-temp.service

[Install]
WantedBy=timers.target
EOF"

ssh root@"${HOST}" "systemctl daemon-reload && systemctl enable --now intel-gpu-temp.timer"
log "Systemd timer actief"

# Direct een eerste run uitvoeren
ssh root@"${HOST}" "systemctl start intel-gpu-temp.service"
log "Eerste run uitgevoerd"

# Resultaat tonen
echo ""
echo "--- GPU temp metric ---"
ssh root@"${HOST}" "cat /var/lib/node_exporter/textfile_collector/intel_gpu_temp.prom 2>/dev/null || echo '  (nog geen output — controleer of i915/xe driver actief is)'"

echo ""
log "Klaar — metric verschijnt als intel_gpu_temperature_celsius in Prometheus"
