#!/bin/bash
# Deploy iperf3 multi-target benchmark naar alle Linux clients
# Gebruik: bash scripts/deploy-iperf3-clients.sh
# Uitvoeren vanuit de root van de metrics-hostinglocal repo

set -e
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }

BENCHMARK_SCRIPT="scripts/iperf3-benchmark.sh"
INSTALL_SCRIPT="scripts/install-iperf3-benchmark.sh"

# Format: "ssh-target:label"
LINUX_CLIENTS=(
    "root@100.81.170.58:PVE-MS01-I9"
    "root@100.94.188.94:PVE-MS01-I5"
    "root@100.119.137.54:NETWORKSERVER"
    "root@100.97.195.23:NUT-SERVER"
    "root@100.103.226.56:FANSERVER"
    "root@100.125.153.71:VPS-HOSTINGLOCAL"
    "root@100.107.226.24:VPS-WORKINGLOCAL"
)

deploy_linux() {
    local SSH_TARGET="${1%%:*}"
    local LABEL="${1##*:}"
    echo ""
    echo "=== $LABEL ($SSH_TARGET) ==="

    if ! ssh -o ConnectTimeout=8 -o BatchMode=yes "$SSH_TARGET" true 2>/dev/null; then
        warn "$LABEL: niet bereikbaar, overgeslagen"
        return
    fi

    scp -q "$BENCHMARK_SCRIPT" "$SSH_TARGET":/usr/local/bin/iperf3-benchmark.sh
    scp -q "$INSTALL_SCRIPT"   "$SSH_TARGET":/tmp/install-iperf3-benchmark.sh
    ssh "$SSH_TARGET" "bash /tmp/install-iperf3-benchmark.sh"
    ok "$LABEL: klaar"
}

echo "=== iPerf3 multi-target client deploy ==="
echo "Benchmark targets: fileserver (192.168.111.30) + networkserver + windowsserver"
echo ""

for CLIENT in "${LINUX_CLIENTS[@]}"; do
    deploy_linux "$CLIENT"
done

echo ""
echo "=== Servers nog in te stellen ==="
warn "NETWORKSERVER: ssh root@100.119.137.54 bash /tmp/install-iperf3-server.sh"
warn "  (SCP eerst: scp scripts/install-iperf3-server.sh root@100.119.137.54:/tmp/)"
warn "WINDOWSSERVER: scripts/setup-iperf3-server-windows.ps1 uitvoeren als Administrator"
warn "WINDOWSSERVER client: scripts/iperf3-benchmark.ps1 instellen via Task Scheduler"
echo ""
ok "Linux client deploy voltooid"
echo ""
echo "Controleer na ~5 min:"
echo "  curl -s 'http://192.168.111.18:9090/api/v1/query?query=network_iperf3_bits_per_second' | python3 -m json.tool | head -40"
