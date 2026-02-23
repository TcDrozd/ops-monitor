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
