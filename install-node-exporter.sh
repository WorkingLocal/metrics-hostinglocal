#!/bin/bash
# Installeer node_exporter op een Linux node
# Uitvoeren als root op de doelserver
# Gebruik: bash install-node-exporter.sh

set -e

VERSION="1.8.2"
ARCH="linux-amd64"

echo "=== node_exporter ${VERSION} installeren ==="

cd /tmp
curl -sLO "https://github.com/prometheus/node_exporter/releases/download/v${VERSION}/node_exporter-${VERSION}.${ARCH}.tar.gz"
tar xzf "node_exporter-${VERSION}.${ARCH}.tar.gz"
cp "node_exporter-${VERSION}.${ARCH}/node_exporter" /usr/local/bin/
chmod +x /usr/local/bin/node_exporter
rm -rf "node_exporter-${VERSION}.${ARCH}"*

# Textfile collector directory voor custom metrics (bv. GPU temp)
mkdir -p /var/lib/node_exporter/textfile_collector
chown nobody:nogroup /var/lib/node_exporter/textfile_collector

# Systemd service
cat > /etc/systemd/system/node_exporter.service << EOF
[Unit]
Description=Prometheus Node Exporter
After=network.target

[Service]
Type=simple
User=nobody
ExecStart=/usr/local/bin/node_exporter \
  --web.listen-address=0.0.0.0:9100 \
  --collector.hwmon \
  --collector.thermal_zone \
  --collector.textfile.directory=/var/lib/node_exporter/textfile_collector
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable node_exporter
systemctl start node_exporter
systemctl is-active node_exporter

echo "✓ node_exporter draait op poort 9100"
