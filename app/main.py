from fastapi import FastAPI
from app.config import settings

app = FastAPI(title="Ops Monitor")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/config")
def config():
    return {
        "portainer_base_url": settings.PORTAINER_BASE_URL,
        "proxmox_stats_url": settings.PROXMOX_STATS_URL,
        "interval": settings.MONITOR_INTERVAL
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
