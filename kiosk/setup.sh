#!/bin/bash
# Grafana Kiosk Setup — METRICSSERVER HDMI display
# Uitvoeren als root op METRICSSERVER
# Vereist: Ubuntu 22.04, Intel HD 630 (HDMI/DP), metrics user bestaat

set -e
METRICS_USER="metrics"
KIOSK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GRAFANA_URL="http://metrics.hostinglocal.be/d/serverrack-kiosk?kiosk&refresh=30s&theme=dark"

echo "=== Grafana Kiosk Setup ==="
echo "User: $METRICS_USER"
echo "URL: $GRAFANA_URL"
echo ""

# Pakketten installeren
echo "[1/5] X11 + kiosk pakketten installeren..."
apt-get update -qq
apt-get install -y --no-install-recommends \
    xserver-xorg \
    xserver-xorg-video-intel \
    x11-xserver-utils \
    openbox \
    unclutter \
    xinit \
    xauth

# Chromium installeren (snap of apt)
echo "[2/5] Chromium installeren..."
if apt-get install -y chromium 2>/dev/null; then
    echo "  chromium (apt) geïnstalleerd"
elif apt-get install -y chromium-browser 2>/dev/null; then
    echo "  chromium-browser (snap/apt) geïnstalleerd"
    # Linger inschakelen zodat snap werkt vanuit tty X session
    loginctl enable-linger "$METRICS_USER" 2>/dev/null || true
else
    echo "  WAARSCHUWING: chromium niet gevonden via apt"
    echo "  Installeer handmatig: snap install chromium"
    echo "  Of voeg Google Chrome repo toe:"
    echo "    wget -q -O- https://dl.google.com/linux/linux_signing_key.pub | apt-key add -"
    echo "    echo 'deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main' > /etc/apt/sources.list.d/google-chrome.list"
    echo "    apt-get update && apt-get install -y google-chrome-stable"
fi

# Getty autologin configureren (tty1 → metrics user)
echo "[3/5] Autologin configureren op tty1..."
mkdir -p /etc/systemd/system/getty@tty1.service.d/
cp "$KIOSK_DIR/autologin.conf" /etc/systemd/system/getty@tty1.service.d/autologin.conf
systemctl daemon-reload
systemctl enable getty@tty1.service

# .bash_profile — start X automatisch bij login op tty1
echo "[4/5] .bash_profile configureren..."
BASH_PROFILE="/home/$METRICS_USER/.bash_profile"
cat > "$BASH_PROFILE" << 'PROFILE'
# Grafana Kiosk — start X op tty1, herstart bij crash
if [[ -z "$DISPLAY" ]] && [[ "$(tty)" = "/dev/tty1" ]]; then
    while true; do
        startx -- -nocursor 2>/tmp/xsession.log
        echo "startx gestopt, herstart over 10s..." >> /tmp/xsession.log
        sleep 10
    done
fi
PROFILE
chown "$METRICS_USER:$METRICS_USER" "$BASH_PROFILE"

# .xinitrc — X sessie configuratie (openbox + chromium kiosk)
echo "[5/5] .xinitrc installeren..."
XINITRC="/home/$METRICS_USER/.xinitrc"
cp "$KIOSK_DIR/xinitrc" "$XINITRC"
chmod +x "$XINITRC"
chown "$METRICS_USER:$METRICS_USER" "$XINITRC"

echo ""
echo "=== Setup klaar ==="
echo ""
echo "Volgende stap: herstart METRICSSERVER"
echo "  sudo reboot"
echo ""
echo "Na reboot:"
echo "  - tty1 logt automatisch in als 'metrics'"
echo "  - X start automatisch"
echo "  - Chromium opent Grafana in kiosk mode"
echo ""
echo "Logs bekijken na reboot:"
echo "  cat /tmp/xsession.log   (X server log)"
echo ""
echo "Kiosk URL: $GRAFANA_URL"
