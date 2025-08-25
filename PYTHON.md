
# Run SyncMover via Python script (aka without Docker)

---

## Linux and macOS

---

1. Install dependencies

```bash
sudo apt update && sudo apt install -y python3 python3-pip
pip3 install requests python-dotenv
```

If your Python environment is externally managed, install via apt:

```bash
sudo apt install python3-dotenv
```

2. Clone and run

(Assuming git is installed)

```bash
git clone https://github.com/lebowski89/syncmover.git
cd syncmover
cp .env.example .env   # edit with your settings
python3 syncmover.py
```

3. Run as a background service (systemd)

Create /etc/systemd/system/syncmover.service:

```ini
[Unit]
Description=SyncMover Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/syncmover/syncmover.py
WorkingDirectory=/opt/syncmover
EnvironmentFile=/opt/syncmover/.env
Restart=always
User=syncmover

[Install]
WantedBy=multi-user.target
```

Enable & start:

```bash
sudo systemctl enable --now syncmover
```

---

## Windows

---

1. Install dependencies

* Install Python 3 from python.org
* Install packages via Windows Powershell:

```powershell
pip install requests python-dotenv
```

2. Clone and run

With Git for Windows installed, VSCode:

```powershell
git clone https://github.com/lebowski89/syncmover.git
cd syncmover
copy .env.example .env   # edit with your settings
python syncmover.py
```

You can also clone via the GitHub SyncMover repository page.

3. Run at startup

Option A: Use Task Scheduler

* Open Task Scheduler → Create Basic Task
* Trigger: "At logon"
* Action: python.exe C:\path\to\syncmover.py
* Start in: C:\path\to\syncmover

Option B: Use NSSM (Non-Sucking Service Manager)

```powershell
nssm install SyncMover "C:\Python311\python.exe" "C:\path\to\syncmover.py"
```

This runs it as a Windows Service.