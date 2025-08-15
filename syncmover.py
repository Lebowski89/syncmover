#!/usr/bin/env python3
"""
Syncthing Hardlink Watcher & Cleaner
------------------------------------
- Watches for Syncthing "FolderCompletion" events
- Hardlinks completed files from sync folders to target folders
- Async cleanup with batching, grace periods, and keep-recent-file support
- Rotating logs with configurable log levels
- Fully environment-variable-driven configuration
- Supports any app name with multiple instances (APP_0, APP_1, etc.)
"""

import os
import requests
import time
import argparse
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from threading import Thread
import re
import shutil
import tempfile

# ======================
# === USER CONFIGURATION VIA ENVIRONMENT VARIABLES ===
# ======================

# Syncthing API
API_KEY = os.getenv("SYNCTHING_API_KEY", "")
HOST = os.getenv("SYNCTHING_HOST", "127.0.0.1")
PORT = int(os.getenv("SYNCTHING_PORT", 8384))
API_TIMEOUT = int(os.getenv("API_TIMEOUT", 15))
API_URL = f"http://{HOST}:{PORT}/rest"
HEADERS = {"X-API-Key": API_KEY}

# Log configuration
LOG_FILE = os.getenv("LOG_FILE", "/logs/syncmover.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_ROTATE_SIZE = int(os.getenv("LOG_ROTATE_SIZE", 5*1024*1024))
LOG_ROTATE_BACKUP = int(os.getenv("LOG_ROTATE_BACKUP", 5))

# Ensure log directory exists safely
log_dir = os.path.dirname(LOG_FILE)
if log_dir and not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir, exist_ok=True)
    except PermissionError:
        tmp_log = tempfile.NamedTemporaryFile(prefix="syncmover_", suffix=".log", delete=False)
        LOG_FILE = tmp_log.name
        tmp_log.close()
        log_dir = os.path.dirname(LOG_FILE)

# Cleanup configuration
CLEANUP_AFTER_HOURS = int(os.getenv("CLEANUP_AFTER_HOURS", 24))
CLEANUP_INTERVAL_MINUTES = int(os.getenv("CLEANUP_INTERVAL_MINUTES", 360))
CLEANUP_BATCH_SIZE = int(os.getenv("CLEANUP_BATCH_SIZE", 100))
KEEP_RECENT_FILES = int(os.getenv("KEEP_RECENT_FILES", 10))

# Grace period configuration
GRACE_PERIOD_MINUTES = int(os.getenv("GRACE_PERIOD_MINUTES", 15))
LOG_GRACE_PERIOD_SKIPS = os.getenv("LOG_GRACE_PERIOD_SKIPS", "True").lower() in ("true", "1")

# File ownership
OWNER_UID = int(os.getenv("OWNER_UID", 1000))
OWNER_GID = int(os.getenv("OWNER_GID", 1000))

# Ignore files/patterns
IGNORE_FILES = set(os.getenv("IGNORE_FILES", ".stfolder").split(","))
IGNORE_PATTERNS = tuple(os.getenv(
    "IGNORE_PATTERNS",
    ".syncthing.,.tmp"
).split(","))

# ======================
# === LOGGING SETUP ===
# ======================
logger = logging.getLogger("SyncMover")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S")

# Rotating file handler
fh = RotatingFileHandler(LOG_FILE, maxBytes=LOG_ROTATE_SIZE, backupCount=LOG_ROTATE_BACKUP)
fh.setFormatter(formatter)
logger.addHandler(fh)

# Console handler
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

# ======================
# === UTILITIES ===
# ======================
def should_ignore(filename):
    if filename in IGNORE_FILES:
        return True
    return any(pattern in filename for pattern in IGNORE_PATTERNS)

def hardlink_file(src, dst, grace_cutoff):
    """Attempt to hardlink a file; fall back to copy if hardlink fails."""
    fname = os.path.basename(src)
    if should_ignore(fname):
        return False

    try:
        mtime = os.path.getmtime(src)
        if mtime >= grace_cutoff:
            if LOG_GRACE_PERIOD_SKIPS:
                logger.debug(f"Skipped (grace period for linking): {src}")
            return False
    except FileNotFoundError:
        return False

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        if os.path.exists(dst):
            logger.debug(f"Skipped duplicate: {src} already exists at {dst}")
            return False
        try:
            os.link(src, dst)
            action = "Hardlinked"
        except (OSError, PermissionError):
            shutil.copy2(src, dst)
            action = "Copied"
        os.chown(dst, OWNER_UID, OWNER_GID)
        logger.info(f"{action}: {src} -> {dst}")
        return True
    except Exception as e:
        logger.error(f"Error linking or copying {src}: {e}")
        return False

def process_folder(src, dst):
    """Walk source folder and hardlink/copy eligible files to destination."""
    moved, skipped = 0, 0
    grace_cutoff = time.time() - GRACE_PERIOD_MINUTES * 60

    for root, _, files in os.walk(src):
        for fname in files:
            if should_ignore(fname):
                continue
            src_path = os.path.join(root, fname)
            rel_path = os.path.relpath(src_path, src)
            dst_path = os.path.join(dst, rel_path)
            if hardlink_file(src_path, dst_path, grace_cutoff):
                moved += 1
            else:
                skipped += 1

    logger.info(f"Processed {moved} files, skipped {skipped} from {src} -> {dst}")

# ======================
# === CLEANUP ===
# ======================
def cleanup_folder_async(path, dry_run=False):
    """Delete old files asynchronously in batches, keeping recent files if configured."""
    def cleanup():
        now = time.time()
        cutoff = now - CLEANUP_AFTER_HOURS * 3600
        grace_cutoff = now - GRACE_PERIOD_MINUTES * 60
        deleted_count = 0
        skipped_due_to_grace = 0
        files_to_delete = []

        # Gather files with modification times
        all_files = []
        for root, _, files in os.walk(path):
            for fname in files:
                if should_ignore(fname):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    mtime = os.path.getmtime(fpath)
                    all_files.append((fpath, mtime))
                except FileNotFoundError:
                    continue

        # Sort newest first and skip recent N files
        all_files.sort(key=lambda x: x[1], reverse=True)
        files_to_consider = all_files[KEEP_RECENT_FILES:]

        for fpath, mtime in files_to_consider:
            if mtime >= grace_cutoff:
                skipped_due_to_grace += 1
                if LOG_GRACE_PERIOD_SKIPS:
                    logger.debug(f"Skipped (grace period for deletion): {fpath}")
                continue
            if mtime < cutoff:
                files_to_delete.append(fpath)

        # Delete in batches
        for i in range(0, len(files_to_delete), CLEANUP_BATCH_SIZE):
            batch = files_to_delete[i:i+CLEANUP_BATCH_SIZE]
            for f in batch:
                try:
                    if dry_run:
                        logger.info(f"[Dry-run] Would delete: {f}")
                    else:
                        os.remove(f)
                        deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting file {f}: {e}")
            if batch and not dry_run:
                logger.info(f"Deleted batch of {len(batch)} files from {path}")

        if not dry_run:
            if deleted_count:
                logger.info(f"Total files deleted from {path}: {deleted_count}")
            if skipped_due_to_grace:
                logger.debug(f"Total files skipped due to grace period: {skipped_due_to_grace}")

    Thread(target=cleanup, daemon=True).start()

# ======================
# === SYNCTHING API ===
# ======================
def get_folder_id_map():
    """Fetch mapping of Syncthing folder labels to folder IDs."""
    try:
        r = requests.get(f"{API_URL}/system/config", headers=HEADERS, timeout=API_TIMEOUT)
        r.raise_for_status()
        cfg = r.json()
        return {f["label"]: f["id"] for f in cfg["folders"]}
    except Exception as e:
        logger.error(f"Failed to fetch folder config: {e}")
        return {}

# ======================
# === DYNAMIC FOLDER LABELS FROM ENV ===
# ======================
def build_folder_labels_from_env():
    """Scan environment for APP_INSTANCE_FOLDER_LABEL, SYNCFOLDER_PATH, SYNCMOVER_PATH."""
    folder_labels = {}
    env_pattern = re.compile(r"(?P<app>[A-Z0-9]+)_(?P<instance>\d+)_FOLDER_LABEL")
    for env_key, folder_label in os.environ.items():
        m = env_pattern.match(env_key)
        if m:
            app = m.group("app")
            instance = m.group("instance")
            syncfolder_path = os.getenv(f"{app}_{instance}_SYNCFOLDER_PATH")
            syncmover_path = os.getenv(f"{app}_{instance}_SYNCMOVER_PATH")
            if syncfolder_path and syncmover_path:
                folder_labels[folder_label] = (syncfolder_path, syncmover_path)
            else:
                logger.warning(f"Missing SYNCFOLDER_PATH or SYNCMOVER_PATH for {env_key}")
    return folder_labels

# ======================
# === MAIN LOOP ===
# ======================
def main_loop(dry_run=False):
    logger.info("Starting Syncthing hardlink watcher with async cleanup and rotating logs...")

    folder_labels = build_folder_labels_from_env()
    if not folder_labels:
        logger.error("No folder labels found in environment variables. Exiting.")
        return

    label_to_id = get_folder_id_map()
    if not label_to_id:
        logger.error("Could not get folder IDs from Syncthing. Exiting.")
        return

    folder_config = {}
    for label, paths in folder_labels.items():
        fid = label_to_id.get(label)
        if fid:
            folder_config[fid] = paths
        else:
            logger.warning(f"No folder ID for label '{label}'")

    last_event_id = 0
    last_cleanup = 0

    while True:
        now = time.time()
        try:
            r = requests.get(f"{API_URL}/events", headers=HEADERS, params={"since": last_event_id}, timeout=60)
            r.raise_for_status()
            events = r.json()

            for event in events:
                last_event_id = event["id"]
                if event["type"] == "FolderCompletion":
                    fid = event["data"].get("folder")
                    if fid in folder_config:
                        src, dst = folder_config[fid]
                        logger.info(f"FolderCompletion detected for '{fid}'")
                        process_folder(src, dst)

            if now - last_cleanup >= CLEANUP_INTERVAL_MINUTES * 60:
                logger.info("Starting periodic async cleanup of syncmover folders...")
                for _, dst in folder_config.values():
                    cleanup_folder_async(dst, dry_run=dry_run)
                last_cleanup = now

        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(5)

# ======================
# === CLI ENTRY POINT ===
# ======================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Syncthing Hardlink Watcher & Cleaner")
    parser.add_argument("--dry-run", action="store_true", help="Run cleanup in dry-run mode (no deletions)")
    parser.add_argument("--log-level", default=LOG_LEVEL, choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Set logging level")
    args = parser.parse_args()

    logger.setLevel(getattr(logging, args.log_level.upper(), logging.INFO))
    main_loop(dry_run=args.dry_run)