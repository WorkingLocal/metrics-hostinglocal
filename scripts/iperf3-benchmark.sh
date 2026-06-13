#!/bin/bash
# iPerf3 bandbreedte benchmark naar FILESERVER
# Schrijft Prometheus textfile metrics voor node_exporter textfile_collector
# Uitvoeren via systemd timer (elk uur) of handmatig

FILESERVER_IP="${IPERF3_TARGET:-192.168.111.30}"
TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}"
PROM_FILE="$TEXTFILE_DIR/iperf3_benchmark.prom"
DURATION="${IPERF3_DURATION:-10}"
HOST=$(hostname -s | tr '[:upper:]' '[:lower:]')

# Detecteer interface richting FILESERVER
IFACE=$(ip route get "$FILESERVER_IP" 2>/dev/null | grep -oP 'dev \K\S+' | head -1 || echo "")

# Bepaal interface type — detecteert ook Proxmox/Linux bridges correct
detect_iface_type() {
    local iface="$1"
    [ -z "$iface" ] && echo "unknown" && return

    if [ -d "/sys/class/net/$iface/wireless" ]; then
        echo "wifi"
        return
    fi

    # Bridge: gebruik snelheid van fysieke member-NIC (niet tap*/veth*)
    local speed_iface="$iface"
    if [ -d "/sys/class/net/$iface/bridge" ]; then
        for member in /sys/class/net/$iface/brif/*; do
            local mname
            mname=$(basename "$member" 2>/dev/null)
            case "$mname" in
                tap*|veth*|vxlan*|bond*) continue ;;
            esac
            if [ -f "/sys/class/net/$mname/speed" ]; then
                speed_iface="$mname"
                break
            fi
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

# Voer iperf3 test uit
RESULT=$(iperf3 -c "$FILESERVER_IP" -t "$DURATION" -J 2>/dev/null || echo "")
IPERF_EXIT=$?

# Parse JSON output
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
    BPS=0
    SUCCESS=0
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
