#!/bin/bash
# Installeert Promtail als systemd service op een Linux host.
# Stuurt logs naar Loki op METRICSSERVER (100.67.19.40:3100 via Tailscale).
#
# Gebruik: sudo bash install-promtail.sh <hostname>
# Voorbeeld: sudo bash install-promtail.sh vm-autoba
#
# Ondersteunde log-bronnen (auto-detect):
#   - Docker containers (als /var/run/docker.sock bestaat)
#   - /var/log/syslog + auth.log + kern.log
#   - Nginx access/error logs (als /var/log/nginx/ bestaat)
#   - Proxmox logs (als /var/log/pve/ bestaat)

set -e

HOSTNAME="${1:-$(hostname)}"
LOKI_URL="http://100.67.19.40:3100/loki/api/v1/push"
PROMTAIL_VERSION="3.3.2"
# TrueNAS SCALE heeft read-only /opt — gebruik /var/lib/promtail/bin
if [ -f /etc/version ] && grep -q "TrueNAS" /etc/version 2>/dev/null; then
    INSTALL_DIR="/var/lib/promtail/bin"
else
    INSTALL_DIR="/opt/promtail"
fi
CONFIG_FILE="/etc/promtail/config.yml"

echo "=== Promtail installer voor host: $HOSTNAME ==="

# Download
mkdir -p "$INSTALL_DIR"
if [ ! -f "$INSTALL_DIR/promtail" ]; then
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  ARCH_SUFFIX="amd64" ;;
        aarch64) ARCH_SUFFIX="arm64" ;;
        *)       echo "Onbekend arch: $ARCH"; exit 1 ;;
    esac
    echo "Downloaden promtail $PROMTAIL_VERSION ($ARCH_SUFFIX)..."
    which unzip >/dev/null 2>&1 || apt-get install -y unzip 2>/dev/null || yum install -y unzip 2>/dev/null || true
    curl -fsSL -o /tmp/promtail.zip \
        "https://github.com/grafana/loki/releases/download/v${PROMTAIL_VERSION}/promtail-linux-${ARCH_SUFFIX}.zip"
    cd /tmp && unzip -o promtail.zip "promtail-linux-${ARCH_SUFFIX}" -d "$INSTALL_DIR"
    mv "$INSTALL_DIR/promtail-linux-${ARCH_SUFFIX}" "$INSTALL_DIR/promtail"
    chmod +x "$INSTALL_DIR/promtail"
    cd -
fi

# Config genereren
mkdir -p /etc/promtail /var/lib/promtail

cat > "$CONFIG_FILE" << ENDCONFIG
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /var/lib/promtail/positions.yaml

clients:
  - url: ${LOKI_URL}

scrape_configs:
ENDCONFIG

# Docker (als beschikbaar)
if [ -S /var/run/docker.sock ]; then
    echo "Docker socket gevonden — Docker log scraping toevoegen"
    cat >> "$CONFIG_FILE" << ENDCONFIG

  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: [__meta_docker_container_name]
        regex: /(.*)
        target_label: container
      - source_labels: [__meta_docker_container_log_stream]
        target_label: stream
      - source_labels: [__meta_docker_container_label_com_docker_compose_service]
        target_label: service
      - target_label: host
        replacement: ${HOSTNAME}
ENDCONFIG
fi

# Systeemlogs
cat >> "$CONFIG_FILE" << ENDCONFIG

  - job_name: syslog
    static_configs:
      - targets: [localhost]
        labels:
          job: syslog
          host: ${HOSTNAME}
          __path__: /var/log/syslog

  - job_name: auth
    static_configs:
      - targets: [localhost]
        labels:
          job: auth
          host: ${HOSTNAME}
          __path__: /var/log/auth.log
ENDCONFIG

# Nginx logs (als beschikbaar)
if [ -d /var/log/nginx ]; then
    echo "Nginx logs gevonden"
    cat >> "$CONFIG_FILE" << ENDCONFIG

  - job_name: nginx
    static_configs:
      - targets: [localhost]
        labels:
          job: nginx
          host: ${HOSTNAME}
          __path__: /var/log/nginx/*.log
ENDCONFIG
fi

# Proxmox logs (als beschikbaar)
if [ -d /var/log/pve ]; then
    echo "Proxmox logs gevonden"
    cat >> "$CONFIG_FILE" << ENDCONFIG

  - job_name: proxmox
    static_configs:
      - targets: [localhost]
        labels:
          job: proxmox
          host: ${HOSTNAME}
          __path__: /var/log/pve/*.log
ENDCONFIG
fi

# systemd service
cat > /etc/systemd/system/promtail.service << ENDSVC
[Unit]
Description=Promtail log shipper
After=network.target

[Service]
Type=simple
ExecStart=${INSTALL_DIR}/promtail -config.file=/etc/promtail/config.yml
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
ENDSVC

systemctl daemon-reload
systemctl enable promtail
systemctl restart promtail
systemctl is-active promtail && echo "Promtail actief op $HOSTNAME" || echo "FOUT: promtail niet gestart"
