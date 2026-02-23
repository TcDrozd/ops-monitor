# ops-monitor

Minimal FastAPI monitor that reads checks from `checks.yml`, runs HTTP/TCP checks in a background loop, and exposes status endpoints.

## Local run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp checks.example.yml checks.yml
./run_dev.sh
```

Default dev server: `http://0.0.0.0:8060` (uvicorn `app.main:app`).

## SQLite persistence

Check state and recent status events are persisted to SQLite.

- Env var: `OPSMONITOR_DB_PATH`
- Local dev example: `OPSMONITOR_DB_PATH=./data/ops-monitor.sqlite3`
- LXC/systemd target path: `/opt/ops-monitor/data/ops-monitor.sqlite3`

`StateStore` hydrates from the DB on startup so `/api/status/*` has the last known state before the next loop completes.

## Config

Environment variables are loaded from `.env` via `python-dotenv` in `app/config.py`.

- `MONITOR_INTERVAL` (seconds)
- `OPSMONITOR_DB_PATH` (SQLite file path)
- Existing integration/env vars remain unchanged (`PORTAINER_*`, `NTFY_*`, `PROXMOX_STATS_URL`)
