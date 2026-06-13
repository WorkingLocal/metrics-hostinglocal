#!/bin/bash
# Prometheus TSDB snapshot backup → FILESERVER
# Runs daily via cron, writes result to textfile_collector for Prometheus monitoring

TEXTFILE_DIR="/var/lib/node_exporter/textfile_collector"
PROM_FILE="$TEXTFILE_DIR/prometheus_backup.prom"
SNAPSHOT_DIR="/var/lib/docker/volumes/metrics_prometheus_data/_data/snapshots"
FILESERVER_HOST="100.72.50.41"
FILESERVER_PORT="221"
FILESERVER_USER="vandrommethomas"
FILESERVER_DEST="/volume1/homes/vandrommethomas/backup-homelab/prometheus-snapshots"
KEEP_SNAPSHOTS=7

JOB="prometheus"
HOST="metricsserver"
START=$(date +%s)

write_metrics() {
  local status=$1
  local duration=$2
  local end=$3
  cat > "${PROM_FILE}.tmp" << EOF
# HELP backup_last_run_unixtime Unix timestamp of last backup run
# TYPE backup_last_run_unixtime gauge
backup_last_run_unixtime{job="${JOB}",host="${HOST}"} ${START}
# HELP backup_last_end_unixtime Unix timestamp of last backup completion
# TYPE backup_last_end_unixtime gauge
backup_last_end_unixtime{job="${JOB}",host="${HOST}"} ${end}
# HELP backup_last_duration_seconds Duration of last backup run in seconds
# TYPE backup_last_duration_seconds gauge
backup_last_duration_seconds{job="${JOB}",host="${HOST}"} ${duration}
# HELP backup_last_status Status of last backup (0=success 1=failed)
# TYPE backup_last_status gauge
backup_last_status{job="${JOB}",host="${HOST}"} ${status}
EOF
  mv "${PROM_FILE}.tmp" "$PROM_FILE"
}

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "Prometheus snapshot backup gestart"

# 1. Snapshot aanmaken via admin API
SNAP_RESPONSE=$(curl -s -XPOST http://localhost:9090/api/v1/admin/tsdb/snapshot)
SNAP_NAME=$(echo "$SNAP_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['name'])" 2>/dev/null)

if [ -z "$SNAP_NAME" ]; then
  log "FOUT: snapshot aanmaken mislukt: $SNAP_RESPONSE"
  END=$(date +%s)
  write_metrics 1 $((END - START)) $END
  exit 1
fi

log "Snapshot aangemaakt: $SNAP_NAME"
SNAP_PATH="$SNAPSHOT_DIR/$SNAP_NAME"

# 2. Transfer naar FILESERVER via tar+ssh (Synology rsync is setuid-root, blokkeert --server mode)
log "Transfer naar FILESERVER..."
SSH_CMD="ssh -p $FILESERVER_PORT -i /root/.ssh/metricsserver_backup_ed25519 -o StrictHostKeyChecking=no -o BatchMode=yes"
SNAP_FILENAME="${SNAP_NAME}.tar.gz"

tar -czf - -C "$SNAPSHOT_DIR" "$SNAP_NAME" | \
  $SSH_CMD "$FILESERVER_USER@$FILESERVER_HOST" \
    "mkdir -p $FILESERVER_DEST && cat > $FILESERVER_DEST/${SNAP_FILENAME}"

RSYNC_EXIT=$?
END=$(date +%s)
DURATION=$((END - START))

if [ $RSYNC_EXIT -ne 0 ]; then
  log "FOUT: transfer mislukt (exit $RSYNC_EXIT)"
  write_metrics 1 $DURATION $END
  exit 1
fi

log "Backup succesvol in ${DURATION}s: ${SNAP_FILENAME}"
write_metrics 0 $DURATION $END

# 3. Oude backups opkuisen op FILESERVER (bewaar max KEEP_SNAPSHOTS)
$SSH_CMD "$FILESERVER_USER@$FILESERVER_HOST" \
  "ls -t $FILESERVER_DEST/*.tar.gz 2>/dev/null | tail -n +$((KEEP_SNAPSHOTS + 1)) | xargs rm -f 2>/dev/null; echo ok"

# 4. Lokale snapshots opkuisen (bewaar max KEEP_SNAPSHOTS)
ls -dt "$SNAPSHOT_DIR"/*/ 2>/dev/null | tail -n +$((KEEP_SNAPSHOTS + 1)) | xargs rm -rf 2>/dev/null

log "Klaar. Snapshot '$SNAP_NAME' naar FILESERVER gesynct."
