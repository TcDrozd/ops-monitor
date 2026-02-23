from fastapi import FastAPI

from app.state import StateStore
from app.runner import loop_forever
from app.config import settings
from app.registry import apply_defaults, load_registry

import threading

app = FastAPI(title="Ops Monitor")
store = StateStore(db_path=settings.OPSMONITOR_DB_PATH)


@app.on_event("startup")
def start_runner():
    t = threading.Thread(
        target=loop_forever,
        args=(store, settings.MONITOR_INTERVAL),
        daemon=True,
    )
    t.start()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def config():
    return {
        "portainer_base_url": settings.PORTAINER_BASE_URL,
        "proxmox_stats_url": settings.PROXMOX_STATS_URL,
        "interval": settings.MONITOR_INTERVAL,
    }


@app.get("/api/registry/raw")
def registry_raw():
    reg = load_registry()
    return reg.model_dump()


@app.get("/api/registry")
def registry_normalized():
    reg = load_registry()
    return {
        "defaults": reg.defaults.model_dump(),
        "checks": apply_defaults(reg),
        "count": len(reg.checks),
    }


@app.get("/api/status/checks")
def status_checks():
    return store.snapshot()


@app.get("/api/status/summary")
def status_summary():
    snap = store.snapshot()
    total = len(snap)
    up = sum(1 for v in snap.values() if v["ok"] is True)
    down = sum(1 for v in snap.values() if v["ok"] is False)
    unknown = sum(1 for v in snap.values() if v["ok"] is None)

    down_list = [v for v in snap.values() if v["ok"] is False]
    return {
        "total": total,
        "up": up,
        "down": down,
        "unknown": unknown,
        "down_checks": down_list,
    }


@app.get("/api/status/events")
def status_events(limit: int = 50):
    return store.events(limit=limit)
