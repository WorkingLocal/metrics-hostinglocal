#!/bin/bash
# Installeer iperf3 benchmark + systemd timer op een Linux host
# Uitvoeren als root op de doelserver
# Gebruik: bash install-iperf3-benchmark.sh [FILESERVER_IP]
# Voorbeeld: bash install-iperf3-benchmark.sh 192.168.111.30

set -e

FILESERVER_IP="${1:-192.168.111.30}"
SCRIPT_DST="/usr/local/bin/iperf3-benchmark.sh"
TEXTFILE_DIR="/var/lib/node_exporter/textfile_collector"

echo "=== iperf3 benchmark installer ==="
echo "  FILESERVER_IP: $FILESERVER_IP"
echo "  Textfile dir:  $TEXTFILE_DIR"

# Installeer iperf3 indien nodig
if ! command -v iperf3 >/dev/null 2>&1; then
    echo "iperf3 installeren..."
    apt-get update -qq && apt-get install -y -q iperf3
    echo "✓ iperf3 geïnstalleerd"
else
    echo "✓ iperf3 al aanwezig: $(iperf3 --version 2>&1 | head -1)"
fi

# Schrijf benchmark script naar /usr/local/bin/
cat > "$SCRIPT_DST" << 'BENCHSCRIPT'
#!/bin/bash
FILESERVER_IP="${IPERF3_TARGET:-192.168.111.30}"
TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}"
PROM_FILE="$TEXTFILE_DIR/iperf3_benchmark.prom"
DURATION="${IPERF3_DURATION:-10}"
HOST=$(hostname -s | tr '[:upper:]' '[:lower:]')

IFACE=$(ip route get "$FILESERVER_IP" 2>/dev/null | grep -oP 'dev \K\S+' | head -1 || echo "")

detect_iface_type() {
    local iface="$1"
    [ -z "$iface" ] && echo "unknown" && return
    if [ -d "/sys/class/net/$iface/wireless" ]; then
        echo "wifi"; return
    fi
    local speed_iface="$iface"
    if [ -d "/sys/class/net/$iface/bridge" ]; then
        for member in /sys/class/net/$iface/brif/*; do
            local mname; mname=$(basename "$member" 2>/dev/null)
            case "$mname" in tap*|veth*|vxlan*|bond*) continue ;; esac
            [ -f "/sys/class/net/$mname/speed" ] && speed_iface="$mname" && break
        done
    fi
    if [ -f "/sys/class/net/$speed_iface/speed" ]; then
        local speed
        speed=$(cat "/sys/class/net/$speed_iface/speed" 2>/dev/null || echo "0")
        case "$speed" in
            10000) echo "lan_10gbe" ;;
            2500)  echo "lan_2_5gbe" ;;
            1000)  echo "lan_1gbe" ;;
            100)   echo "lan_100mbe" ;;
            *)     echo "lan" ;;
        esac
    else
        echo "lan"
    fi
}

IFACE_TYPE=$(detect_iface_type "$IFACE")
TIMESTAMP=$(date +%s)

RESULT=$(iperf3 -c "$FILESERVER_IP" -t "$DURATION" -J 2>/dev/null || echo "")
IPERF_EXIT=$?

if [ $IPERF_EXIT -eq 0 ] && [ -n "$RESULT" ]; then
    BPS=$(echo "$RESULT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(int(d['end']['sum_received']['bits_per_second']))
except:
    print(0)
" 2>/dev/null || echo "0")
    [ -z "$BPS" ] && BPS=0
    if [ "$BPS" -gt 0 ]; then SUCCESS=1; else SUCCESS=0; fi
else
    BPS=0; SUCCESS=0
fi

LABELS="hostname=\"$HOST\",interface=\"${IFACE:-none}\",interface_type=\"$IFACE_TYPE\""
TMP="$PROM_FILE.tmp"

cat > "$TMP" << EOF
# HELP network_iperf3_to_fileserver_bits_per_second Gemeten bandbreedte naar FILESERVER (bits/sec)
# TYPE network_iperf3_to_fileserver_bits_per_second gauge
network_iperf3_to_fileserver_bits_per_second{$LABELS} $BPS
# HELP network_iperf3_to_fileserver_success 1=test geslaagd, 0=gefaald
# TYPE network_iperf3_to_fileserver_success gauge
network_iperf3_to_fileserver_success{$LABELS} $SUCCESS
# HELP network_iperf3_to_fileserver_last_run_timestamp Unix timestamp van laatste test
# TYPE network_iperf3_to_fileserver_last_run_timestamp gauge
network_iperf3_to_fileserver_last_run_timestamp{$LABELS} $TIMESTAMP
EOF

mv "$TMP" "$PROM_FILE"
MBPS=$(( BPS / 1000000 ))
echo "[$HOST] iperf3 → FILESERVER: ${MBPS} Mbps via ${IFACE:-?} ($IFACE_TYPE)"
BENCHSCRIPT

chmod +x "$SCRIPT_DST"
echo "✓ Script geïnstalleerd: $SCRIPT_DST"

# Textfile directory aanmaken indien nodig
mkdir -p "$TEXTFILE_DIR"
echo "✓ Textfile dir: $TEXTFILE_DIR"

# Systemd service unit
cat > /etc/systemd/system/iperf3-benchmark.service << EOF
[Unit]
Description=iPerf3 bandbreedte benchmark naar FILESERVER
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$SCRIPT_DST
Environment=IPERF3_TARGET=$FILESERVER_IP
Environment=TEXTFILE_DIR=$TEXTFILE_DIR
StandardOutput=journal
StandardError=journal
EOF

# Systemd timer unit (elk uur, random delay 0-2min)
cat > /etc/systemd/system/iperf3-benchmark.timer << EOF
[Unit]
Description=iPerf3 benchmark elk uur

[Timer]
OnBootSec=5min
OnUnitActiveSec=1h
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable iperf3-benchmark.timer
systemctl start iperf3-benchmark.timer

echo ""
echo "=== Eerste test uitvoeren ==="
systemctl start iperf3-benchmark.service

echo ""
echo "✓ iperf3-benchmark timer actief (elk uur)"
echo ""
echo "Nuttige commando's:"
echo "  systemctl status iperf3-benchmark.timer"
echo "  journalctl -u iperf3-benchmark.service -n 20"
echo "  cat $TEXTFILE_DIR/iperf3_benchmark.prom"
