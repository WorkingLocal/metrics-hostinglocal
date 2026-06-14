#!/bin/bash
# display-ctrl.sh on|off
# Schakel de HDMI display in of uit via DPMS (X11 DISPLAY=:2)
export DISPLAY=:2
export XAUTHORITY=/home/metrics/.Xauthority

case "$1" in
    on)
        /usr/bin/xset dpms force on
        /usr/bin/xset s reset
        ;;
    off)
        /usr/bin/xset dpms force off
        ;;
    *)
        echo "Gebruik: $0 on|off" >&2
        exit 1
        ;;
esac
