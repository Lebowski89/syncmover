# SyncMover

This service watches Syncthing folder completion events, hardlinks files from sync folders to media folders, and optionally cleans up old files.

Table of Contents
------

1. [Features](#Features)
2. [Requirements](#Requirements)
3. [Settings](#Settings)
4. [Deploy: Docker Run](#Run)
5. [Deploy: Docker Run .env File](#Run)
6. [Deploy: Docker Compose](#Compose)
7. [Deploy: Docker Compose .env File](#Env2)
8. [Handling Sensitive Variables](#Secrets)
9. [Deployment Tips](#Deploy)
10. [Contributing](#Contributing)
11. [Support](#Coffee)

---

<a name="Features"/>

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

<a name="Requirements"/>

## Requirements

- Python (Non-Docker)
- Docker
- Syncthing running and accessible from the container  
- Sync and media folders on same volume/pool if hardlinking

---

<a name="Settings"/>

## Settings

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

### File Cleanup (Global)

| Variable                   | Description                                                    |
| -------------------------- | -------------------------------------------------------------- |
| `DRY_RUN`                  | true = no deletions, only logs (default: false)                |
| `CLEANUP_AFTER_HOURS`      | Delete files older than X hours (default: 24)                  |
| `CLEANUP_INTERVAL_MINUTES` | Run cleanup every X minutes (default: 360)                     |
| `CLEANUP_BATCH_SIZE`       | Max files to delete per cleanup run (default: 100)             |
| `KEEP_RECENT_FILES`        | How many recent files to spare from cleanup (default: 10)      |
| `GRACE_PERIOD_MINUTES`     | Minimum age before file can be deleted or linked (default: 15) |
| `LOG_GRACE_PERIOD_SKIPS`   | Skip grace period file logs (default: True)                    |

### File Ownership

| Variable     | Description                          |
| -------------| -------------------------------------|
| `OWNER_UID`  | File/Folder User ID (default: 1000)  |
| `OWNER_GID`  | File/Folder Group ID (default: 1000) |

### Ignore Rules

| Variable          | Description                                                           |
| ----------------- | --------------------------------------------------------------        |
| `IGNORE_FILES`    | Comma-separated list of filenames to ignore (default: `.stfolder`)    |
| `IGNORE_PATTERNS` | Comma-separated substrings to ignore (default: `.syncthing.`)         |

### Folder Configuration

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

<a name="Run"/>

## Deploy: Docker Run (Example)

```bash
docker run -d \
  --name=syncmover \
  --restart unless-stopped \
  -v /host/data:/data \
  -v /host/logs:/logs \
  -e SYNCTHING_API_KEY_FILE="SomeAPIKey" \
  -e SYNCTHING_HOST="127.0.0.1" \
  -e SYNCTHING_PORT="8384" \
  -e API_TIMEOUT="15" \
  -e LOG_FILE="/logs/syncmover.log" \
  -e LOG_LEVEL="INFO" \
  -e LOG_ROTATE_SIZE="5242880" \
  -e LOG_ROTATE_BACKUP="5" \
  -e DRY_RUN="false" \
  -e CLEANUP_AFTER_HOURS="24" \
  -e CLEANUP_INTERVAL_MINUTES="360" \
  -e CLEANUP_BATCH_SIZE="100" \
  -e KEEP_RECENT_FILES="10" \
  -e GRACE_PERIOD_MINUTES="15" \
  -e LOG_GRACE_PERIOD_SKIPS="true" \
  -e OWNER_UID="1000" \
  -e OWNER_GID="1000" \
  -e IGNORE_FILES=".stfolder" \
  -e IGNORE_PATTERNS=".syncthing.,.tmp" \
  -e MOVIES_0_LABEL="Movies" \
  -e MOVIES_0_SYNC_PATH="/data/sync/movies" \
  -e MOVIES_0_MOVER_PATH="/data/media/movies" \
  -e MOVIES_0_CLEANUP="true" \
  -e MOVIES_1_LABEL="Movies-4K" \
  -e MOVIES_1_SYNC_PATH="/data/sync/movies-4k" \
  -e MOVIES_1_MOVER_PATH="/data/media/movies-4k" \
  -e MOVIES_1_CLEANUP="true" \
  -e MOVIES_1_CLEANUP_AFTER_HOURS="24" \
  -e MOVIES_1_CLEANUP_INTERVAL_MINUTES="60" \
  -e MOVIES_1_CLEANUP_BATCH_SIZE="20" \
  -e MOVIES_1_KEEP_RECENT_FILES="5" \
  -e MOVIES_1_GRACE_PERIOD_MINUTES="10" \
  -e TV_0_LABEL="TVShows" \
  -e TV_0_SYNC_PATH="/data/sync/tv" \
  -e TV_0_MOVER_PATH="/data/media/tv" \
  -e TV_0_CLEANUP="true" \
  -e TV_0_CLEANUP_AFTER_HOURS="48" \
  -e TV_0_CLEANUP_INTERVAL_MINUTES="120" \
  -e TV_0_CLEANUP_BATCH_SIZE="10" \
  -e TV_0_KEEP_RECENT_FILES="3" \
  -e TV_0_GRACE_PERIOD_MINUTES="5" \
  -e DOCS_0_FOLDER_LABEL="Documents" \
  -e DOCS_0_SYNC_PATH="/data/sync/docs" \
  -e DOCS_0_MOVER_PATH="/data/media/docs" \
  -e DOCS_0_CLEANUP="false" \
  lebowski89/syncmover:latest
```

<a name="Env1"/>

### Docker Run .env file:

1. Copy .env.example → /path/to/env/syncmover.env and fill in your Syncthing API key and folder paths.
2. Reference the syncmover.env file in your Docker Run:

```bash
docker run -d \
  --name=syncmover \
  --restart unless-stopped \
  -v /host/data:/data \
  -v /host/logs:/logs \
  --env-file /host/syncmover.env \
  lebowski89/syncmover:latest
```

<a name="Compose"/>

## Deploy: Docker Compose (Example)

```bash
services:
  syncmover:
    image: lebowski89/syncmover:latest
    container_name: syncmover
    restart: unless-stopped
    environment:

      # Syncthing Connection
      SYNCTHING_API_KEY_FILE: /run/secrets/syncthing_api_key
      SYNCTHING_HOST: "127.0.0.1"
      SYNCTHING_PORT: "8384"
      API_TIMEOUT: "15"

      # Logging
      LOG_FILE: "/logs/syncmover.log"
      LOG_LEVEL: "INFO"
      LOG_ROTATE_SIZE: "5242880"
      LOG_ROTATE_BACKUP: "5"

      # File Cleanup
      DRY_RUN: "false"
      CLEANUP_AFTER_HOURS: "24"
      CLEANUP_INTERVAL_MINUTES: "360"
      CLEANUP_BATCH_SIZE: "100"
      KEEP_RECENT_FILES: "10"
      GRACE_PERIOD_MINUTES: "15"
      LOG_GRACE_PERIOD_SKIPS: "true"

      # File Ownership
      OWNER_UID: "1000"
      OWNER_GID: "1000"

      # Ignore Rules
      IGNORE_FILES: ".stfolder"
      IGNORE_PATTERNS: ".syncthing.,.tmp"

      # Folder Mappings

      # Movies 
      MOVIES_0_LABEL: "Movies"
      MOVIES_0_SYNC_PATH: "/data/sync/movies"
      MOVIES_0_MOVER_PATH: "/data/media/movies"
      MOVIES_0_CLEANUP: "true"  ## Cleanup will occurr using global cleanup settings

      # Movies-4K
      MOVIES_1_LABEL: "Movies-4K"
      MOVIES_1_SYNC_PATH: "/data/sync/movies-4k"
      MOVIES_1_MOVER_PATH: "/data/media/movies-4k"
      MOVIES_1_CLEANUP: "true"  ## Cleanup while overriding global settings
      MOVIES_1_CLEANUP_AFTER_HOURS: "24"
      MOVIES_1_CLEANUP_INTERVAL_MINUTES: "60"
      MOVIES_1_CLEANUP_BATCH_SIZE: "20"
      MOVIES_1_KEEP_RECENT_FILES: "5"
      MOVIES_1_GRACE_PERIOD_MINUTES: "10"

      # TV
      TV_0_LABEL: "TVShows"
      TV_0_SYNC_PATH: "/data/sync/tv"
      TV_0_MOVER_PATH: "/data/media/tv"
      TV_0_CLEANUP: "true"  ## Cleanup while overriding global settings again
      TV_0_CLEANUP_AFTER_HOURS: "48"
      TV_0_CLEANUP_INTERVAL_MINUTES: "120"
      TV_0_CLEANUP_BATCH_SIZE: "10"
      TV_0_KEEP_RECENT_FILES: "3"
      TV_0_GRACE_PERIOD_MINUTES: "5"

      # Documents
      DOCS_0_LABEL: 'Documents'
      DOCS_0_SYNC_PATH: '/data/sync/docs'
      DOCS_0_MOVER_PATH: '/data/media/docs'
      DOCS_0_CLEANUP: "false"  ## No cleanup for this folder
    volumes:
      - /host/data:/data
      - /host/logs:/logs
    secrets:
      - syncthing_api_key

secrets:
  syncthing_api_key:
    file: ./secrets/syncthing_api_key.txt
```
<a name="Env2"/>

### Docker Compose .env file:

1. Copy .env.example → .env and fill in your Syncthing API key and folder paths.
2. Reference the .env file in docker-compose.yml:

```bash
services:
  syncmover:
    env_file:
      - .env
```

<a name="Secrets"/>

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

<a name="Deploy"/>

## Deployment Tips
1. Keep sensitive environment variables in a .env file or use Docker secrets.
2. Use a single bind mount for both your sync and media folder (for hardlinking)
3. Monitor logs to confirm correct hardlinking and cleanup.

<a name="Contributing"/>

## Contributing
- Fork the repo and submit pull requests for new features or bug fixes.
- Use GitHub Issues for bug reports or feature requests.

<a name="Support"/>

## Support

<a href="https://buymeacoffee.com/lebowski89" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>