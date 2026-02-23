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
- `NTFY_URL` (base ntfy URL, e.g. `http://192.168.50.XXX:80`)
- `NTFY_TOPIC` (ntfy topic name)
- Existing integration/env vars remain unchanged (`PORTAINER_*`, `PROXMOX_STATS_URL`)

## Alerts Test Endpoint

Use this endpoint to validate ntfy configuration without waiting for a real failure.

```bash
curl -X POST "http://127.0.0.1:8060/api/alerts/test?check_id=open-webui"
```

- Endpoint: `POST /api/alerts/test?check_id=...`
- Behavior:
  - Validates `NTFY_URL` + `NTFY_TOPIC` are configured
  - Validates `check_id` exists in the normalized registry
  - Sends a test notification to ntfy
