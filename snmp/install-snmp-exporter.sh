#!/bin/bash
# Installeer snmp_exporter op NETWORKSERVER als systemd service
# Uitvoeren als root op de doelserver
# Gebruik: bash install-snmp-exporter.sh

set -e

VERSION="0.26.0"
ARCH="linux-amd64"
PORT="9116"

GREEN='\033[0;32m'
NC='\033[0m'
log() { echo -e "${GREEN}✓${NC} $1"; }

echo "=== snmp_exporter ${VERSION} installeren ==="

cd /tmp
curl -sLO "https://github.com/prometheus/snmp_exporter/releases/download/v${VERSION}/snmp_exporter-${VERSION}.${ARCH}.tar.gz"
tar xzf "snmp_exporter-${VERSION}.${ARCH}.tar.gz"

cp "snmp_exporter-${VERSION}.${ARCH}/snmp_exporter" /usr/local/bin/
chmod +x /usr/local/bin/snmp_exporter
log "binary geïnstalleerd"

# snmp.yml bevat module-definities (if_mib, etc.)
mkdir -p /etc/snmp_exporter
cp "snmp_exporter-${VERSION}.${ARCH}/snmp.yml" /etc/snmp_exporter/snmp.yml
log "snmp.yml geplaatst in /etc/snmp_exporter/"

rm -rf "snmp_exporter-${VERSION}.${ARCH}"*

# Systemd service
cat > /etc/systemd/system/snmp_exporter.service << EOF
[Unit]
Description=Prometheus SNMP Exporter
After=network.target

[Service]
Type=simple
User=nobody
ExecStart=/usr/local/bin/snmp_exporter \
  --config.file=/etc/snmp_exporter/snmp.yml \
  --web.listen-address=0.0.0.0:${PORT}
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable snmp_exporter
systemctl start snmp_exporter
systemctl is-active snmp_exporter

echo ""
log "snmp_exporter draait op poort ${PORT}"
echo "Test: curl 'http://localhost:${PORT}/snmp?target=192.168.111.1&module=if_mib'"
