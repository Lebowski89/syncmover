#!/usr/bin/env bash
set -e

echo "========================================"
echo "Starting SyncMover container..."
echo "LOG_FILE: ${LOG_FILE:-/logs/syncmover.log}"
echo "LOG_LEVEL: ${LOG_LEVEL:-INFO}"
echo "DRY_RUN: ${DRY_RUN:-false}"
echo "----------------------------------------"
echo "Detected folders and cleanup settings:"

# Loop through all FOLDER_*_LABEL env vars
for label_var in $(env | grep -E '^FOLDER_[0-9]+_LABEL=' | sort); do
    folder_label=$(echo "$label_var" | cut -d '=' -f2)
    index=$(echo "$label_var" | grep -oP '(?<=FOLDER_)[0-9]+')
    sync_path_var="FOLDER_${index}_SYNC_PATH"
    mover_path_var="FOLDER_${index}_MOVER_PATH"
    cleanup_var="FOLDER_${index}_CLEANUP"
    cleanup_after_var="FOLDER_${index}_CLEANUP_AFTER_HOURS"
    cleanup_interval_var="FOLDER_${index}_CLEANUP_INTERVAL_MINUTES"
    batch_var="FOLDER_${index}_CLEANUP_BATCH_SIZE"
    keep_var="FOLDER_${index}_KEEP_RECENT_FILES"
    grace_var="FOLDER_${index}_GRACE_PERIOD_MINUTES"
    log_grace_var="FOLDER_${index}_LOG_GRACE_PERIOD_SKIPS"

    sync_path="${!sync_path_var}"
    mover_path="${!mover_path_var}"
    cleanup="${!cleanup_var:-true}"
    cleanup_after="${!cleanup_after_var:-24}"
    cleanup_interval="${!cleanup_interval_var:-360}"
    batch_size="${!batch_var:-100}"
    keep_recent="${!keep_var:-10}"
    grace_period="${!grace_var:-15}"
    log_grace="${!log_grace_var:-true}"

    echo "Folder '$folder_label':"
    echo "  SYNC_PATH: $sync_path"
    echo "  MOVER_PATH: $mover_path"
    echo "  CLEANUP: $cleanup"
    echo "  CLEANUP_AFTER_HOURS: $cleanup_after"
    echo "  CLEANUP_INTERVAL_MINUTES: $cleanup_interval"
    echo "  BATCH_SIZE: $batch_size"
    echo "  KEEP_RECENT_FILES: $keep_recent"
    echo "  GRACE_PERIOD_MINUTES: $grace_period"
    echo "  LOG_GRACE_PERIOD_SKIPS: $log_grace"
    echo "----------------------------------------"

    # Ensure directories exist
    [ -d "$sync_path" ] || mkdir -p "$sync_path"
    [ -d "$mover_path" ] || mkdir -p "$mover_path"
done

echo "All folders configured. Launching SyncMover..."
exec python /app/syncmover.py