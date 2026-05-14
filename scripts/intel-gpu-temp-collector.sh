#!/bin/bash
# Textfile collector: Intel GPU temperatuur via i915/xe hwmon driver
# Schrijft naar /var/lib/node_exporter/textfile_collector/intel_gpu_temp.prom
# Gebruik: elke minuut via systemd timer (zie deploy-intel-gpu-temp.sh)

TEXTFILE_DIR="/var/lib/node_exporter/textfile_collector"
OUTPUT_TMP="${TEXTFILE_DIR}/intel_gpu_temp.prom.tmp"
OUTPUT="${TEXTFILE_DIR}/intel_gpu_temp.prom"

mkdir -p "$TEXTFILE_DIR"

GPU_TEMP_FILE=""
GPU_NAME=""

# Zoek Intel GPU hwmon (i915 of xe driver)
for hwmon_path in /sys/class/hwmon/hwmon*/; do
    name=$(cat "${hwmon_path}name" 2>/dev/null || echo "")
    if [[ "$name" == "i915" ]] || [[ "$name" == "xe" ]]; then
        if [[ -f "${hwmon_path}temp1_input" ]]; then
            GPU_TEMP_FILE="${hwmon_path}temp1_input"
            GPU_NAME="$name"
            break
        fi
    fi
done

cat > "$OUTPUT_TMP" << 'HEADER'
# HELP intel_gpu_temperature_celsius Intel GPU temperatuur in Celsius
# TYPE intel_gpu_temperature_celsius gauge
HEADER

if [[ -n "$GPU_TEMP_FILE" ]]; then
    RAW=$(cat "$GPU_TEMP_FILE" 2>/dev/null || echo "0")
    CELSIUS=$(awk "BEGIN {printf \"%.1f\", $RAW/1000}")
    echo "intel_gpu_temperature_celsius{driver=\"${GPU_NAME}\"} ${CELSIUS}" >> "$OUTPUT_TMP"
fi

mv "$OUTPUT_TMP" "$OUTPUT"
