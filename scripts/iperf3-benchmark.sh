#!/bin/bash
# iPerf3 multi-target bandbreedte benchmark
# Schrijft Prometheus textfile metrics voor node_exporter textfile_collector
# Uitvoeren via systemd timer (elk uur) of handmatig

TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}"
PROM_FILE="$TEXTFILE_DIR/iperf3_benchmark.prom"
DURATION="${IPERF3_DURATION:-10}"
HOST=$(hostname -s | tr '[:upper:]' '[:lower:]')

# Targets: "IP:naam" — voeg toe of verwijder naar behoefte
# Gebruik lokale IPs voor LAN-hosts, Tailscale voor cross-segment
TARGETS=(
    "192.168.111.30:fileserver"
    "192.168.111.16:networkserver"
    "192.168.111.205:windowsserver"
)

detect_iface_type() {
    local iface="$1"
    [ -z "$iface" ] && echo "unknown" && return
    if [ -d "/sys/class/net/$iface/wireless" ]; then echo "wifi"; return; fi
    local speed_iface="$iface"
    if [ -d "/sys/class/net/$iface/bridge" ]; then
        for member in /sys/class/net/$iface/brif/*; do
            local mname; mname=$(basename "$member" 2>/dev/null)
            case "$mname" in tap*|veth*|vxlan*|bond*) continue ;; esac
            [ -f "/sys/class/net/$mname/speed" ] && speed_iface="$mname" && break
        done
    fi
    if [ -f "/sys/class/net/$speed_iface/speed" ]; then
        local speed; speed=$(cat "/sys/class/net/$speed_iface/speed" 2>/dev/null || echo "0")
        case "$speed" in
            10000) echo "lan_10gbe"  ;;
            2500)  echo "lan_2_5gbe" ;;
            1000)  echo "lan_1gbe"   ;;
            100)   echo "lan_100mbe" ;;
            *)     echo "lan"        ;;
        esac
    else
        echo "lan"
    fi
}

TMP="$PROM_FILE.tmp"
TIMESTAMP=$(date +%s)

{
    echo "# HELP network_iperf3_bits_per_second Gemeten bandbreedte naar target (bits/sec)"
    echo "# TYPE network_iperf3_bits_per_second gauge"
    echo "# HELP network_iperf3_success 1=test geslaagd, 0=gefaald"
    echo "# TYPE network_iperf3_success gauge"
    echo "# HELP network_iperf3_last_run_timestamp Unix timestamp van laatste test"
    echo "# TYPE network_iperf3_last_run_timestamp gauge"
} > "$TMP"

for TARGET_DEF in "${TARGETS[@]}"; do
    TARGET_IP="${TARGET_DEF%%:*}"
    TARGET_NAME="${TARGET_DEF##*:}"

    IFACE=$(ip route get "$TARGET_IP" 2>/dev/null | grep -oP 'dev \K\S+' | head -1 || echo "")
    IFACE_TYPE=$(detect_iface_type "$IFACE")

    RESULT=$(iperf3 -c "$TARGET_IP" -t "$DURATION" -J 2>/dev/null || echo "")
    BPS=0; SUCCESS=0
    if [ -n "$RESULT" ]; then
        BPS=$(echo "$RESULT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(int(d['end']['sum_received']['bits_per_second']))
except:
    print(0)
" 2>/dev/null || echo "0")
        [ -z "$BPS" ] && BPS=0
        [ "$BPS" -gt 0 ] && SUCCESS=1
    fi

    LABELS="hostname=\"$HOST\",target=\"$TARGET_NAME\",interface=\"${IFACE:-none}\",interface_type=\"$IFACE_TYPE\""
    {
        echo "network_iperf3_bits_per_second{$LABELS} $BPS"
        echo "network_iperf3_success{$LABELS} $SUCCESS"
        echo "network_iperf3_last_run_timestamp{$LABELS} $TIMESTAMP"
    } >> "$TMP"

    MBPS=$(( BPS / 1000000 ))
    echo "[$HOST] iperf3 → $TARGET_NAME ($TARGET_IP): ${MBPS} Mbps via ${IFACE:-?} ($IFACE_TYPE)"
done

mv "$TMP" "$PROM_FILE"
