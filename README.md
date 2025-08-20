# SyncMover

This service watches Syncthing folder completion events, hardlinks files from sync folders to media folders, and optionally cleans up old files. 

---

## Features

- Watches Syncthing 'FolderCompletion' events.
- Hardlinks synced files to target folders.
- Falls back to file copy when unable to hardlink
- Async cleanup with batching, grace periods, and keep-recent-file support
- Fully environment-variable-driven configuration.
- Supports multiple folders (e.g., Movies, TV).
- Rotating logs and configurable log levels.
- Ignores unwanted files (scene notes, samples, cover art, etc.)
- Ensures correct UID/GID ownership on hardlinked files
- Grace periods to avoid touching newly added files
- Async cleanup with batching to prevent I/O spikes

---

## Requirements

- Syncthing running and accessible from the container  
- Sync and media folders on same volume/pool if hardlinking

---

## Environment Variables

### Syncthing Connection

| Variable            | Description                                                  |
| ------------------- | -------------------------------------------------------------|
| `SYNCTHING_API_KEY` | Syncthing API key (can be set via file for Docker secrets)   |
| `SYNCTHING_HOST`    | Syncthing host or IP (default: `127.0.0.1`)                  |
| `SYNCTHING_PORT`    | Syncthing WebUI port (default: `8384`)                       |
| `API_TIMEOUT`       | Timeout (seconds) for API requests (default: `15`)           |

### Logging

| Variable                   | Description                                                   |
| -------------------------- | ------------------------------------------------------------- |
| `LOG_FILE`                 | Name of /logs file (default: `/logs/syncmover.log`)           |
| `LOG_LEVEL`                | DEBUG, INFO, WARNING or ERROR (default: `INFO`)               |
| `LOG_ROTATE_SIZE`          | Size (Bytes) of log file before rotating (default: `5242880`) |
| `LOG_ROTATE_BACKUP`        | Max number of rotated logs to keep (default: `5`)             |

### Behavior Controls

| Variable                   | Description                                                    |
| -------------------------- | -------------------------------------------------------------- |
| `DRY_RUN`                  | true = no deletions, only logs (default: false)                |
| `CLEANUP_AFTER_HOURS`      | Delete files older than X hours (default: 24)                  |
| `CLEANUP_INTERVAL_MINUTES` | Run cleanup every X minutes (default: 360)                     |
| `CLEANUP_BATCH_SIZE`       | Max files per cleanup batch (default: 100)                     |
| `KEEP_RECENT_FILES`        | Never delete this many most recent (default: 10)               |
| `GRACE_PERIOD_MINUTES`     | Minimum age before file can be deleted or linked (default: 15) |
| `LOG_GRACE_PERIOD_SKIPS`   | Log files skipped due to grace period (default: True)          |

### File Ownership

| Variable     | Description                          |
| -------------| -------------------------------------|
| `OWNER_UID`  | File/Folder User ID (default: 1000)  |
| `OWNER_GID`  | File/Folder Group ID (default: 1000) |

### Ignored Files

| Variable          | Description                                                           |
| ----------------- | --------------------------------------------------------------        |
| `IGNORE_FILES`    | Comma-separated list of filenames to ignore (default: `.stfolder`)    |
| `IGNORE_PATTERNS` | Comma-separated substrings to ignore (default: `.syncthing.`)         |

### Folder Configuration

| Variable                          | Description                                   |
| --------------------------------- | ----------------------------------------------|
| `<FOLDERNAME>_<INDEX>_LABEL`      | Sync Folder label (as listed in syncthing)    |
| `<FOLDERNAME>_<INDEX>_SYNC_PATH`  | Local path where folder syncs via syncthing   |
| `<FOLDERNAME>_<INDEX>_MOVER_PATH` | Local path for files moved by syncmover       |

### Example Folder Configuration

```bash
MOVIES_0_FOLDER_LABEL: 'Movies'
MOVIES_0_SYNC_PATH: '/data/sync/radarr'
MOVIES_0_MOVER_PATH: '/data/media/movies'

MOVIES_1_FOLDER_LABEL: 'Movies4K'
MOVIES_1_SYNC_PATH: '/data/sync/radarr4k'
MOVIES_1_MOVER_PATH: '/data/media/movies-4k'

TV_0_LABEL: 'TVShows'
TV_0_SYNC_PATH: '/data/sync/tv'
TV_0_MOVER_PATH: '/data/media/tv'

WARTHUNDERSECRETDOCS_0_FOLDER_LABEL: 'sekkreettdokuments'
WARTHUNDERSECRETDOCS_0_SYNC_PATH: '/data/sync/totallynotsecretdocs'
WARTHUNDERSECRETDOCS_0_MOVER_PATH: '/data/media/totallynotsecretdocs'
```

**Notes:**
- How many folders you configure is up to you
- What you have for `<FOLDERNAME>` is up to you
- The `<INDEX>` allows for multiple folders of the same `<FOLDERNAME>`
- The value for `FOLDER_LABEL` must match the label set for that folder within syncthing
- The value for both paths is from the container path (/data) to your media
- As mentioned before in these docs, a single mount path for the sync and media folder allows hardlinking
- You can add additional sync and media paths to the container but files will be copied instead of hardlinked.

## Example docker-compose.yml

```bash
services:
  syncmover:
    image: lebowski89/syncmover:latest
    container_name: syncmover
    restart: unless-stopped
    environment:
      # Syncthing API
      SYNCTHING_API_KEY_FILE: /run/secrets/syncthing_api_key
      SYNCTHING_HOST: "127.0.0.1"
      SYNCTHING_PORT: "8384"
      API_TIMEOUT: "15"

      # Logging
      LOG_FILE: "/logs/syncmover.log"
      LOG_LEVEL: "INFO"
      LOG_ROTATE_SIZE: "5242880"
      LOG_ROTATE_BACKUP: "5"
      DRY_RUN: "false"

      # Cleanup
      CLEANUP_AFTER_HOURS: "24"
      CLEANUP_INTERVAL_MINUTES: "360"
      CLEANUP_BATCH_SIZE: "100"
      KEEP_RECENT_FILES: "10"
      GRACE_PERIOD_MINUTES: "15"
      LOG_GRACE_PERIOD_SKIPS: "true"

      # File ownership
      OWNER_UID: "1000"
      OWNER_GID: "1000"

      # Ignore files
      IGNORE_FILES: ".stfolder"
      IGNORE_PATTERNS: ".syncthing.,.tmp"

      # Folder mappings
      MOVIES_0_LABEL: "Movies"
      MOVIES_0_SYNC_PATH: "/data/sync/movies"
      MOVIES_0_MOVER_PATH: "/data/media/movies"

      MOVIES_1_LABEL: "Movies-4K"
      MOVIES_1_SYNC_PATH: "/data/sync/movies-4k"
      MOVIES_1_MOVER_PATH: "/data/media/movies-4k"

      TV_0_LABEL: "TVShows"
      TV_0_SYNC_PATH: "/data/sync/tv"
      TV_0_MOVER_PATH: "/data/media/tv"

    volumes:
      - /host/data:/data
      - /host/logs:/logs

    secrets:
      - syncthing_api_key

secrets:
  syncthing_api_key:
    file: ./secrets/syncthing_api_key.txt
```

### Using an .env file:

1. Copy .env.example → .env and fill in your actual Syncthing API key and folder paths.
2. Reference the .env file in docker-compose.yml:

```bash
services:
  syncmover:
    env_file:
      - .env
```

### Handling sensitive variables

For sensitive values you can use Docker secrets. For example:

```bash
services:
  syncmover:
    environment:
      SYNCTHING_API_KEY_FILE: /run/secrets/syncthing_api_key
    secrets:
      - syncthing_api_key

secrets:
  syncthing_api_key:
    file: ./secrets/syncthing_api_key.txt
```

## Deployment Tips
1. Keep sensitive environment variables in a .env file or use Docker secrets.
2. Use a single bind mount for both your sync and media folder (for hardlinking)
3. Monitor logs to confirm correct hardlinking and cleanup.

## Contributing
- Fork the repo and submit pull requests for new features or bug fixes.
- Use GitHub Issues for bug reports or feature requests.