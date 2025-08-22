#!/usr/bin/env python3

import os, re, time, requests, logging, shutil, tempfile
from threading import Thread
from logging.handlers import RotatingFileHandler

################################
# USER CONFIG VIA ENV VARIABLES
################################
def get_env(name: str, default: str = "") -> str:
    file_key = f"{name}_FILE"
    if file_key in os.environ:
        path = os.environ[file_key]
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            raise RuntimeError(f"Failed to read secret from {path}: {e}")
    return os.getenv(name, default)

# Syncthing Connection
API_KEY = get_env("SYNCTHING_API_KEY")
HOST = get_env("SYNCTHING_HOST", "127.0.0.1")
PORT = int(get_env("SYNCTHING_PORT", "8384"))
API_TIMEOUT = int(get_env("API_TIMEOUT", "15"))
API_URL = f"http://{HOST}:{PORT}/rest"
HEADERS = {"X-API-Key": API_KEY}

# Logging
LOG_FILE = get_env("LOG_FILE", "/logs/syncmover.log")
LOG_LEVEL = get_env("LOG_LEVEL", "INFO").upper()
LOG_ROTATE_SIZE = int(get_env("LOG_ROTATE_SIZE", str(5*1024*1024)))
LOG_ROTATE_BACKUP = int(get_env("LOG_ROTATE_BACKUP", "5"))

DRY_RUN = get_env("DRY_RUN", "false").lower() in ("true", "1", "yes")

# File Cleanup (used if not overridden per folder)
CLEANUP_AFTER_HOURS = int(get_env("CLEANUP_AFTER_HOURS", "24"))
CLEANUP_INTERVAL_MINUTES = int(get_env("CLEANUP_INTERVAL_MINUTES", "360"))
CLEANUP_BATCH_SIZE = int(get_env("CLEANUP_BATCH_SIZE", "100"))
KEEP_RECENT_FILES = int(get_env("KEEP_RECENT_FILES", "10"))
GRACE_PERIOD_MINUTES = int(get_env("GRACE_PERIOD_MINUTES", "15"))
LOG_GRACE_PERIOD_SKIPS = get_env("LOG_GRACE_PERIOD_SKIPS", "True").lower() in ("true", "1")

# File Ownership
OWNER_UID = int(get_env("OWNER_UID", "1000"))
OWNER_GID = int(get_env("OWNER_GID", "1000"))

# Ignore Rules
IGNORE_FILES = set(get_env("IGNORE_FILES", ".stfolder").split(","))
IGNORE_PATTERNS = tuple(get_env("IGNORE_PATTERNS", ".syncthing.,.tmp").split(","))

################################
# LOGGING SETUP
################################
log_dir = os.path.dirname(LOG_FILE)
if log_dir and not os.path.exists(log_dir):
    try: os.makedirs(log_dir, exist_ok=True)
    except PermissionError:
        tmp_log = tempfile.NamedTemporaryFile(prefix="syncmover_", suffix=".log", delete=False)
        LOG_FILE = tmp_log.name
        tmp_log.close()
        log_dir = os.path.dirname(LOG_FILE)

logger = logging.getLogger("SyncMover")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%Y-%m-%d %H:%M:%S")
fh = RotatingFileHandler(LOG_FILE, maxBytes=LOG_ROTATE_SIZE, backupCount=LOG_ROTATE_BACKUP)
fh.setFormatter(formatter)
logger.addHandler(fh)
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

################################
# UTILITIES
################################
def should_ignore(filename):
    if filename in IGNORE_FILES: return True
    return any(pattern in filename for pattern in IGNORE_PATTERNS)

def hardlink_file(src, dst, grace_cutoff):
    fname = os.path.basename(src)
    if should_ignore(fname): return False

    try:
        mtime = os.path.getmtime(src)
        if grace_cutoff >= 0 and mtime >= grace_cutoff:
            if LOG_GRACE_PERIOD_SKIPS: logger.debug(f"Skipped (grace period for linking): {src}")
            return False
    except FileNotFoundError: return False

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        logger.debug(f"Skipped duplicate: {src} already exists at {dst}")
        return False

    try:
        try:
            os.link(src, dst)
            action, log_func = "Hardlinked", logger.info
        except (OSError, PermissionError):
            with open(src, "rb") as fsrc, open(dst, "wb") as fdst: shutil.copyfileobj(fsrc, fdst)
            shutil.copystat(src, dst)
            action, log_func = "Copied", logger.warning

        try: os.chown(dst, OWNER_UID, OWNER_GID)
        except PermissionError: pass

        log_func(f"{action}: {src} -> {dst}")
        return True
    except Exception as e:
        logger.error(f"Error linking or copying {src}: {e}")
        return False

def process_folder(src, dst):
    moved, skipped = 0, 0
    grace_cutoff = time.time() - GRACE_PERIOD_MINUTES * 60
    for root, _, files in os.walk(src):
        for fname in files:
            if should_ignore(fname): continue
            src_path = os.path.join(root, fname)
            rel_path = os.path.relpath(src_path, src)
            dst_path = os.path.join(dst, rel_path)
            if hardlink_file(src_path, dst_path, grace_cutoff): moved += 1
            else: skipped += 1
    logger.info(f"Processed {moved} files, skipped {skipped} from {src} -> {dst}")

################################
# CLEANUP
################################
def cleanup_folder_async(path, dry_run=False, keep_recent_override=None):
    def cleanup():
        now = time.time()
        cutoff = now - CLEANUP_AFTER_HOURS * 3600
        grace_cutoff = now - GRACE_PERIOD_MINUTES * 60
        deleted_count, skipped_due_to_grace, files_to_delete = 0, 0, []
        all_files = []

        for root, _, files in os.walk(path):
            for fname in files:
                if should_ignore(fname): continue
                fpath = os.path.join(root, fname)
                try: mtime = os.path.getmtime(fpath); all_files.append((fpath, mtime))
                except FileNotFoundError: continue

        all_files.sort(key=lambda x: x[1], reverse=True)
        keep_count = keep_recent_override if keep_recent_override is not None else KEEP_RECENT_FILES
        files_to_consider = all_files[keep_count:]

        for fpath, mtime in files_to_consider:
            if mtime >= grace_cutoff:
                skipped_due_to_grace += 1
                if LOG_GRACE_PERIOD_SKIPS: logger.debug(f"Skipped (grace period for deletion): {fpath}")
                continue
            if mtime < cutoff: files_to_delete.append(fpath)

        for i in range(0, len(files_to_delete), CLEANUP_BATCH_SIZE):
            batch = files_to_delete[i:i+CLEANUP_BATCH_SIZE]
            for f in batch:
                try:
                    if dry_run: logger.info(f"[Dry-run] Would delete: {f}")
                    else: os.remove(f); deleted_count += 1
                except Exception as e: logger.error(f"Error deleting file {f}: {e}")
            if batch and not dry_run: logger.info(f"Deleted batch of {len(batch)} files from {path}")

        if not dry_run:
            if deleted_count: logger.info(f"Total files deleted from {path}: {deleted_count}")
            if skipped_due_to_grace: logger.debug(f"Total files skipped due to grace period: {skipped_due_to_grace}")

    t = Thread(target=cleanup, daemon=True)
    t.start()
    return t

################################
# SYNCTHING API
################################
def get_folder_id_map():
    try:
        r = requests.get(f"{API_URL}/system/config", headers=HEADERS, timeout=API_TIMEOUT)
        r.raise_for_status()
        cfg = r.json()
        return {f["label"]: f["id"] for f in cfg["folders"]}
    except Exception as e:
        logger.error(f"Failed to fetch folder config: {e}")
        return {}

################################
# PER FOLDER ENV CONFIG
################################
def get_folder_cleanup_settings():  # MODIFIED
    folder_cleanup_config = {}
    env_pattern = re.compile(r"(?P<folder>[A-Z0-9]+)_(?P<index>\d+)_LABEL")

    for env_key, folder_label in os.environ.items():
        m = env_pattern.match(env_key)
        if m:
            folder = m.group("folder")
            index = m.group("index")
            sync_path = os.getenv(f"{folder}_{index}_SYNC_PATH")
            mover_path = os.getenv(f"{folder}_{index}_MOVER_PATH")
            cleanup_enabled = os.getenv(f"{folder}_{index}_CLEANUP", "true").lower() in ("true", "1", "yes")
            cleanup_after_hours = int(os.getenv(f"{folder}_{index}_CLEANUP_AFTER_HOURS", str(CLEANUP_AFTER_HOURS)))
            cleanup_interval_minutes = int(os.getenv(f"{folder}_{index}_CLEANUP_INTERVAL_MINUTES", str(CLEANUP_INTERVAL_MINUTES)))
            cleanup_batch_size = int(os.getenv(f"{folder}_{index}_CLEANUP_BATCH_SIZE", str(CLEANUP_BATCH_SIZE)))
            keep_recent_files = int(os.getenv(f"{folder}_{index}_KEEP_RECENT_FILES", str(KEEP_RECENT_FILES)))
            grace_period_minutes = int(os.getenv(f"{folder}_{index}_GRACE_PERIOD_MINUTES", str(GRACE_PERIOD_MINUTES)))
            log_grace_skips = os.getenv(f"{folder}_{index}_LOG_GRACE_PERIOD_SKIPS", str(LOG_GRACE_PERIOD_SKIPS)).lower() in ("true", "1", "yes")

            if not sync_path or not mover_path:
                logger.warning(f"Skipping {folder_label}: missing SYNC_PATH or MOVER_PATH")
                continue

            folder_cleanup_config[folder_label] = {
                "sync_path": sync_path,
                "mover_path": mover_path,
                "cleanup_enabled": cleanup_enabled,
                "cleanup_after_hours": cleanup_after_hours,
                "cleanup_interval_minutes": cleanup_interval_minutes,
                "cleanup_batch_size": cleanup_batch_size,
                "keep_recent_files": keep_recent_files,
                "grace_period_minutes": grace_period_minutes,
                "log_grace_skips": log_grace_skips
            }

    if not folder_cleanup_config:
        logger.warning("No valid folders found in environment variables!")

    logger.info("=== FOLDER CONFIGURATION ===")
    for label, cfg in folder_cleanup_config.items():
        logger.info(
            f"{label}: SYNC='{cfg['sync_path']}', MOVER='{cfg['mover_path']}', "
            f"CLEANUP={'ON' if cfg['cleanup_enabled'] else 'OFF'}, "
            f"AFTER_HOURS={cfg['cleanup_after_hours']}, INTERVAL_MIN={cfg['cleanup_interval_minutes']}, "
            f"BATCH={cfg['cleanup_batch_size']}, KEEP_RECENT={cfg['keep_recent_files']}, "
            f"GRACE_MIN={cfg['grace_period_minutes']}, LOG_GRACE={cfg['log_grace_skips']}"
        )

    return folder_cleanup_config

################################
# MAIN LOOP UPDATE
################################
def main_loop(dry_run=False):
    logger.info("Starting Syncthing hardlink watcher with async cleanup and rotating logs...")

    folder_labels = get_folder_cleanup_settings()
    if not folder_labels:
        logger.error("No folder labels found in environment variables. Exiting.")
        return

    label_to_id = get_folder_id_map()
    if not label_to_id:
        logger.error("Could not get folder IDs from Syncthing. Exiting.")
        return

    folder_config = {}
    for label, cfg in folder_labels.items():
        fid = label_to_id.get(label)
        if fid: folder_config[fid] = cfg
        else: logger.warning(f"No folder ID for label '{label}'")

    last_event_id, last_cleanup = 0, 0

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
                        src = folder_config[fid]["sync_path"]
                        dst = folder_config[fid]["mover_path"]
                        logger.info(f"FolderCompletion detected for '{fid}'")
                        process_folder(src, dst)

            # Per-folder cleanup
            for _, cfg in folder_config.items():
                if cfg["cleanup_enabled"] and now - last_cleanup >= cfg["cleanup_interval_minutes"]*60:
                    cleanup_folder_async(
                        cfg["mover_path"],
                        dry_run=dry_run,
                        keep_recent_override=cfg["keep_recent_files"]
                    )
            last_cleanup = now

        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(5)

################################
# ENTRY POINT
################################
if __name__ == "__main__":
    main_loop(dry_run=DRY_RUN)