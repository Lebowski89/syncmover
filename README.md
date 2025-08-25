# SyncMover

This service watches Syncthing folder completion events, hardlinks files from sync folders to media folders, and optionally cleans up old files.

---

## Features

- Watches Syncthing 'FolderCompletion' events
- Hardlinks synced files to target folders
- Falls back to file copy when unable to hardlink
- Async cleanup with batching, grace periods, and keep-recent-file support
- Fully environment-variable-driven configuration
- Supports multiple folders (e.g., Movies, TV)
- Rotating logs and configurable log levels
- Ignores unwanted files (scene notes, samples, cover art, etc.)
- Ensures correct UID/GID ownership on hardlinked files
- Grace periods to avoid touching newly added files
- Async cleanup with batching to prevent I/O spikes.

---

## Requirements

- Python (Non-Docker)
- Docker
- Syncthing running and accessible from the container  
- Sync and media folders on same volume/pool if hardlinking

---

## Settings

See [SETTINGS.md](SETTINGS.md)

---

## Deploy

### [Docker](DOCKER.md) ###

---

## Deployment Tips
1. Keep sensitive environment variables in a .env file or use Docker secrets.
2. Use a single bind mount for both your sync and media folder (for hardlinking)
3. Monitor logs to confirm correct hardlinking and cleanup.

---

## Contributing
- Fork the repo and submit pull requests for new features or bug fixes.
- Use GitHub Issues for bug reports or feature requests.

---

## Support

<a href="https://buymeacoffee.com/lebowski89" target="_blank"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" alt="Buy Me A Coffee" style="height: 41px !important;width: 174px !important;box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;" ></a>