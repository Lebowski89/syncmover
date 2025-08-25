# Settings / Environmental Variables

### Syncthing Connection ###

| Variable            | Description                                                  |
| ------------------- | -------------------------------------------------------------|
| `SYNCTHING_API_KEY` | Syncthing API key (can be set via file for Docker secrets)   |
| `SYNCTHING_HOST`    | Syncthing host or IP (default: `127.0.0.1`)                  |
| `SYNCTHING_PORT`    | Syncthing WebUI port (default: `8384`)                       |
| `API_TIMEOUT`       | Timeout (seconds) for API requests (default: `15`)           |

### Logging ###

| Variable                   | Description                                                   |
| -------------------------- | ------------------------------------------------------------- |
| `LOG_FILE`                 | Name of /logs file (default: `/logs/syncmover.log`)           |
| `LOG_LEVEL`                | DEBUG, INFO, WARNING or ERROR (default: `INFO`)               |
| `LOG_ROTATE_SIZE`          | Size (Bytes) of log file before rotating (default: `5242880`) |
| `LOG_ROTATE_BACKUP`        | Max number of rotated logs to keep (default: `5`)             |

### File Cleanup (Global) ###

| Variable                   | Description                                                    |
| -------------------------- | -------------------------------------------------------------- |
| `DRY_RUN`                  | true = no deletions, only logs (default: false)                |
| `CLEANUP_AFTER_HOURS`      | Delete files older than X hours (default: 24)                  |
| `CLEANUP_INTERVAL_MINUTES` | Run cleanup every X minutes (default: 360)                     |
| `CLEANUP_BATCH_SIZE`       | Max files to delete per cleanup run (default: 100)             |
| `KEEP_RECENT_FILES`        | How many recent files to spare from cleanup (default: 10)      |
| `GRACE_PERIOD_MINUTES`     | Minimum age before file can be deleted or linked (default: 15) |
| `LOG_GRACE_PERIOD_SKIPS`   | Skip grace period file logs (default: True)                    |

### File Ownership ###

| Variable     | Description                          |
| -------------| -------------------------------------|
| `OWNER_UID`  | File/Folder User ID (default: 1000)  |
| `OWNER_GID`  | File/Folder Group ID (default: 1000) |

### Ignore Rules ###

| Variable          | Description                                                           |
| ----------------- | --------------------------------------------------------------        |
| `IGNORE_FILES`    | Comma-separated list of filenames to ignore (default: `.stfolder`)    |
| `IGNORE_PATTERNS` | Comma-separated substrings to ignore (default: `.syncthing.`)         |

### Folder Configuration ###

| Variable                                         | Description                                                |
| ------------------------------------------------ | -----------------------------------------------------------|
| `<FOLDERNAME>_<INDEX>_LABEL`                     | Sync Folder label (as listed in syncthing)                 |
| `<FOLDERNAME>_<INDEX>_SYNC_PATH`                 | Local path where folder syncs via syncthing                |
| `<FOLDERNAME>_<INDEX>_MOVER_PATH`                | Local path for files moved by syncmover                    |
| `<FOLDERNAME>_<INDEX>_CLEANUP`                   | Whether to allow SyncMover to cleanup folder files         |

**The below variables are optional. SyncMover will use global cleanup settings if not provided**

| Variable                                         | Description                                                |
| ------------------------------------------------ | -----------------------------------------------------------|
| `<FOLDERNAME>_<INDEX>_CLEANUP_AFTER_HOURS`       | Delete folder files older than X hours                     |
| `<FOLDERNAME>_<INDEX>_CLEANUP_INTERVAL_MINUTES`  | Run folder cleanup every X minutes                         |
| `<FOLDERNAME>_<INDEX>_CLEANUP_BATCH_SIZE`        | Max folder files to delete per cleanup run                 |
| `<FOLDERNAME>_<INDEX>_KEEP_RECENT_FILES`         | How many recent folder files to spare from cleanup         |
| `<FOLDERNAME>_<INDEX>_GRACE_PERIOD_MINUTES`      | Minimum age before folder files can be deleted or linked   |
| `<FOLDERNAME>_<INDEX>_LOG_GRACE_PERIOD_SKIPS`    | Skip grace period folder files logs (default: True)        |

**Notes:**
- No limit for how many folders you configure.
- What you have for `<FOLDERNAME>` is up to you.
- The `<INDEX>` allows for multiple folders of the same `<FOLDERNAME>`.
- The value for `FOLDER_LABEL` must match the label set for that folder within syncthing.
- The value for both paths is from the container path (/data) to your media.
- As mentioned before in these docs, a single mount path for the sync and media folder allows hardlinking.
- You can add additional sync and media paths to the container but files will be copied instead of hardlinked.
- Once you've set `<FOLDER_INDEX_CLEANUP>` to `true` or `false`,  the other folder cleanup variables are optional.