#!/bin/bash
# Zet iperf3 server daemon op op Synology FILESERVER (DSM 7.x)
# Uitvoeren op FILESERVER via SSH:
#   ssh -p 221 vandrommethomas@100.72.50.41
#   sudo bash /tmp/fileserver-iperf3-server.sh
#
# DSM gebruikt /usr/local/etc/rc.d/ voor startup scripts

IPERF3_BIN="/usr/local/bin/iperf3"
RC_SCRIPT="/usr/local/etc/rc.d/iperf3-server.sh"
LOG_FILE="/tmp/iperf3-server.log"

echo "=== iperf3 server setup FILESERVER (DSM) ==="

# Controleer iperf3
if [ ! -x "$IPERF3_BIN" ]; then
    echo "✗ iperf3 niet gevonden op $IPERF3_BIN"
    exit 1
fi
echo "✓ iperf3 aanwezig: $($IPERF3_BIN --version 2>&1 | head -1)"

# Stop eventueel lopende instantie
pkill -f "iperf3 -s" 2>/dev/null && echo "  Bestaande server gestopt" || true

# Schrijf DSM rc.d startup script
cat > "$RC_SCRIPT" << 'EOF'
#!/bin/sh
IPERF3_BIN="/usr/local/bin/iperf3"
LOG_FILE="/tmp/iperf3-server.log"

case "$1" in
  start)
    if pgrep -f "iperf3 -s" > /dev/null; then
        echo "iperf3 server al actief"
    else
        $IPERF3_BIN -s -D --logfile "$LOG_FILE"
        echo "iperf3 server gestart (poort 5201)"
    fi
    ;;
  stop)
    pkill -f "iperf3 -s" 2>/dev/null || true
    echo "iperf3 server gestopt"
    ;;
  status)
    if pgrep -f "iperf3 -s" > /dev/null; then
        echo "iperf3 server actief (poort 5201)"
    else
        echo "iperf3 server NIET actief"
    fi
    ;;
  *)
    echo "Gebruik: $0 {start|stop|status}"
    exit 1
    ;;
esac
EOF

chmod +x "$RC_SCRIPT"
echo "✓ Startup script: $RC_SCRIPT"

# Start server nu
$IPERF3_BIN -s -D --logfile "$LOG_FILE"
sleep 1

if pgrep -f "iperf3 -s" > /dev/null; then
    echo "✓ iperf3 server draait op poort 5201"
    echo "  Logs: tail -f $LOG_FILE"
else
    echo "✗ iperf3 server kon niet starten"
    cat "$LOG_FILE" 2>/dev/null || echo "(geen log)"
    exit 1
fi

echo ""
echo "Nuttige commando's:"
echo "  $RC_SCRIPT status"
echo "  $RC_SCRIPT stop"
echo "  pgrep -a iperf3"
echo "  tail -f $LOG_FILE"
