#!/bin/bash
# Herbruikbare library voor backup/rclone job monitoring via Prometheus textfile_collector.
# Gebruik:
#   source /opt/metrics-hostinglocal/scripts/backup-metrics-lib.sh
#   backup_start "rclone-muziek" "ai-node-i9"
#   ... voer de job uit ...
#   backup_end $? "rclone-muziek" "ai-node-i9"   # $? = exit code van de job

TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}"

backup_start() {
  local job="$1"
  local host="${2:-$(hostname)}"
  export _BACKUP_START_$(echo "${job}${host}" | tr -dc '[:alnum:]')=$(date +%s)
  export _BACKUP_JOB="$job"
  export _BACKUP_HOST="$host"
}

backup_end() {
  local exit_code="$1"
  local job="${2:-$_BACKUP_JOB}"
  local host="${3:-$_BACKUP_HOST}"
  local start_var="_BACKUP_START_$(echo "${job}${host}" | tr -dc '[:alnum:]')"
  local start="${!start_var:-$(date +%s)}"
  local end=$(date +%s)
  local duration=$((end - start))
  local status=0
  [ "$exit_code" -ne 0 ] && status=1

  local prom_file="${TEXTFILE_DIR}/backup_$(echo "${job}" | tr -dc '[:alnum:]_').prom"

  cat > "${prom_file}.tmp" << EOF
# HELP backup_last_run_unixtime Unix timestamp of last backup run start
# TYPE backup_last_run_unixtime gauge
backup_last_run_unixtime{job="${job}",host="${host}"} ${start}
# HELP backup_last_end_unixtime Unix timestamp of last backup completion
# TYPE backup_last_end_unixtime gauge
backup_last_end_unixtime{job="${job}",host="${host}"} ${end}
# HELP backup_last_duration_seconds Duration of last backup in seconds
# TYPE backup_last_duration_seconds gauge
backup_last_duration_seconds{job="${job}",host="${host}"} ${duration}
# HELP backup_last_status Status of last backup (0=success 1=failed)
# TYPE backup_last_status gauge
backup_last_status{job="${job}",host="${host}"} ${status}
EOF
  mv "${prom_file}.tmp" "$prom_file"
}
