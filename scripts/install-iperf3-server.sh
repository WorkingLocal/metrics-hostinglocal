#!/bin/bash
# Installeer iperf3 als server daemon op een Linux host (systemd service)
# Bedoeld voor NETWORKSERVER (Proxmox bare metal, 100.119.137.54)
# Gebruik: bash install-iperf3-server.sh
# Of via deploy: ssh root@100.119.137.54 bash /tmp/install-iperf3-server.sh

set -e

PORT="${1:-5201}"

echo "=== iperf3 server installer (poort $PORT) ==="

if ! command -v iperf3 >/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -q iperf3
fi
echo "✓ iperf3: $(iperf3 --version 2>&1 | head -1)"

cat > /etc/systemd/system/iperf3-server.service << EOF
[Unit]
Description=iPerf3 server daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=nobody
ExecStart=/usr/bin/iperf3 -s --port $PORT
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable iperf3-server
systemctl restart iperf3-server
sleep 1
systemctl is-active iperf3-server

echo ""
echo "✓ iperf3 server draait op poort $PORT"
echo "  Test: iperf3 -c $(hostname -I | awk '{print $1}') -t 5"
echo "  Log:  tail -f /var/log/iperf3-server.log"
