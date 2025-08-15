# SyncMover

**Syncthing Hardlink Watcher & Cleaner**

SyncMover watches Syncthing folders for completed transfers, hardlinks completed files to import/processing folders (e.g., Radarr, Sonarr, Lidarr, Whisparr), and periodically cleans up old files asynchronously.  

---

## Features

- Ignores unwanted files (scene notes, samples, cover art, etc.)
- Ensures correct UID/GID ownership on hardlinked files
- Waits for Syncthing folder completion before processing
- Grace periods to avoid touching newly added files
- Async cleanup with batching to prevent I/O spikes
- Rotating log files with adjustable log levels and retention
- Configurable via environment variables for Docker or local execution
- Supports multiple instances of any app type (Radarr, Sonarr, Lidarr, etc.)

---

## Requirements

- Syncthing running and accessible from the container  

---

## Environment Variables

### Syncthing Connection

| Variable      | Description                                                |
| ------------- | ---------------------------------------------------------- |
| `API_KEY`     | Syncthing API key (can be set via file for Docker secrets) |
| `HOST`        | Syncthing host or IP                                       |
| `PORT`        | Syncthing WebUI port                                       |
| `API_TIMEOUT` | Timeout (seconds) for API requests (default: 15)           |

### Cleanup & Hardlink Settings

| Variable                   | Description                                                    |
| -------------------------- | -------------------------------------------------------------- |
| `CLEANUP_AFTER_HOURS`      | Delete files older than this from destination (default: 24)    |
| `CLEANUP_INTERVAL_MINUTES` | How often cleanup runs (default: 360)                          |
| `CLEANUP_BATCH_SIZE`       | Number of files deleted per batch (default: 100)               |
| `KEEP_RECENT_FILES`        | Always keep this many recent files, even if old (default: 10)  |
| `GRACE_PERIOD_MINUTES`     | Minimum age before file can be deleted or linked (default: 15) |
| `LOG_GRACE_PERIOD_SKIPS`   | Log files skipped due to grace period (default: True)          |
| `OWNER_UID` / `OWNER_GID`  | File ownership for hardlinked files (default: 1000 / 1000)     |

### Ignored Files

| Variable          | Description                                                           |
| ----------------- | --------------------------------------------------------------        |
| `IGNORE_FILES`    | Comma-separated list of filenames to ignore (default: `.stfolder`)    |
| `IGNORE_PATTERNS` | Comma-separated substrings to ignore (default: `.syncthing.`)         |

### App Folder Configuration (Multiple Instances)

**Each app instance uses three variables:**

```bash
<APP>_<INDEX>_FOLDER_LABEL
<APP>_<INDEX>_SYNCFOLDER_PATH
<APP>_<INDEX>_SYNCMOVER_PATH
```

**Example for two Radarr instances:**

```bash
RADARR_0_FOLDER_LABEL=Movies
RADARR_0_SYNCFOLDER_PATH=/sync/radarr
RADARR_0_SYNCMOVER_PATH=/media/radarr

RADARR_1_FOLDER_LABEL=Movies4K
RADARR_1_SYNCFOLDER_PATH=/sync/radarr_4k
RADARR_1_SYNCMOVER_PATH=/media/radarr_4k
```

Similarly, use SONARR_0_..., LIDARR_0_..., or any custom app name.

## Example docker-compose.yml

```bash
services:
  syncmover:
    image: lebowski89/syncmover:latest
    container_name: syncmover
    restart: unless-stopped
    environment:
      # Syncthing API
      API_KEY_FILE: /run/secrets/syncthing_api_key
      HOST: syncthing.local
      PORT: 8384

      # Cleanup & hardlink settings
      CLEANUP_AFTER_HOURS: 24
      CLEANUP_INTERVAL_MINUTES: 360
      CLEANUP_BATCH_SIZE: 100
      KEEP_RECENT_FILES: 10
      GRACE_PERIOD_MINUTES: 15
      LOG_GRACE_PERIOD_SKIPS: "True"
      OWNER_UID: 1000
      OWNER_GID: 1000

      # Ignore files/patterns
      IGNORE_FILES: ".stfolder"
      IGNORE_PATTERNS: ".syncthing.,.tmp,.nfo,sample,.txt,.jpg,.jpeg,.png,.sfv,.md5,.crc"

      # App folder labels (example: Radarr instance 0 and 1)
      RADARR_0_FOLDER_LABEL: "radarr_sync"
      RADARR_0_SYNCFOLDER_PATH: "/sync/radarr_0"
      RADARR_0_SYNCMOVER_PATH: "/media/movies_0"

      RADARR_1_FOLDER_LABEL: "radarr_4k"
      RADARR_1_SYNCFOLDER_PATH: "/sync/radarr_1"
      RADARR_1_SYNCMOVER_PATH: "/media/movies_1"

      SONARR_0_FOLDER_LABEL: "sonarr_sync"
      SONARR_0_SYNCFOLDER_PATH: "/sync/sonarr_0"
      SONARR_0_SYNCMOVER_PATH: "/media/tv_0"

      LIDARR_0_FOLDER_LABEL: "lidarr_sync"
      LIDARR_0_SYNCFOLDER_PATH: "/sync/lidarr_0"
      LIDARR_0_SYNCMOVER_PATH: "/media/music_0"

    secrets:
      - syncthing_api_key

    volumes:
      - ./logs:/logs
      - ./sync:/sync      # Syncthing synced folders
      - ./media:/media    # Output folders for hardlinks

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

3. For sensitive values like API_KEY, you can instead use Docker secrets. For example:

```bash
secrets:
  syncthing_api_key:
    file: ./secrets/api_key.txt

services:
  syncmover:
    secrets:
      - syncthing_api_key
```

## Logs
- Logs are written to /logs/syncmover.log in the container.
- Rotating logs prevent unbounded growth.
- Log level and rotation size can be configured via environment variables or CLI arguments if running outside Docker.

## Deployment Tips
1. Keep sensitive environment variables in a .env file or use Docker secrets.
2. Use volumes to persist logs and synced media.
3. Test each app instance individually before scaling to multiple instances.
4. Monitor logs to confirm correct hardlinking and cleanup.

## Contributing
- Fork the repo and submit pull requests for new features or bug fixes.
- Use GitHub Issues for bug reports or feature requests.