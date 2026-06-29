#!/bin/bash
# Installeer iperf3 benchmark systemd timer op een Linux host
# Vereiste: iperf3-benchmark.sh moet al op /usr/local/bin/iperf3-benchmark.sh staan
#           (geplaatst door deploy-iperf3-clients.sh via SCP)
# Handmatig gebruik:
#   scp scripts/iperf3-benchmark.sh root@<host>:/usr/local/bin/iperf3-benchmark.sh
#   scp scripts/install-iperf3-benchmark.sh root@<host>:/tmp/
#   ssh root@<host> bash /tmp/install-iperf3-benchmark.sh

set -e

SCRIPT_DST="/usr/local/bin/iperf3-benchmark.sh"
TEXTFILE_DIR="/var/lib/node_exporter/textfile_collector"

echo "=== iperf3 benchmark installer ==="

if ! command -v iperf3 >/dev/null 2>&1; then
    echo "iperf3 installeren..."
    apt-get update -qq && apt-get install -y -q iperf3
fi
echo "✓ iperf3: $(iperf3 --version 2>&1 | head -1)"

[ -f "$SCRIPT_DST" ] || { echo "✗ $SCRIPT_DST ontbreekt — voer eerst SCP uit"; exit 1; }
chmod +x "$SCRIPT_DST"
echo "✓ Script: $SCRIPT_DST"

mkdir -p "$TEXTFILE_DIR"
echo "✓ Textfile dir: $TEXTFILE_DIR"

cat > /etc/systemd/system/iperf3-benchmark.service << EOF
[Unit]
Description=iPerf3 multi-target bandbreedte benchmark
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$SCRIPT_DST
Environment=TEXTFILE_DIR=$TEXTFILE_DIR
StandardOutput=journal
StandardError=journal
EOF

cat > /etc/systemd/system/iperf3-benchmark.timer << EOF
[Unit]
Description=iPerf3 benchmark elk uur

[Timer]
OnActiveSec=2min
OnUnitActiveSec=1h
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable iperf3-benchmark.timer
systemctl restart iperf3-benchmark.timer
echo "✓ Timer actief (elk uur)"

echo ""
echo "=== Eerste test uitvoeren ==="
systemctl start iperf3-benchmark.service

echo ""
echo "✓ Klaar — controleer resultaat:"
echo "  journalctl -u iperf3-benchmark.service -n 30"
echo "  cat $TEXTFILE_DIR/iperf3_benchmark.prom"
