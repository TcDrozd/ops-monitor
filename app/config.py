import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PORTAINER_BASE_URL: str = os.getenv("PORTAINER_BASE_URL")
    PORTAINER_API_KEY: str = os.getenv("PORTAINER_API_KEY")
    NTFY_URL: str = os.getenv("NTFY_URL")
    NTFY_TOPIC: str = os.getenv("NTFY_TOPIC")
    PROXMOX_STATS_URL: str = os.getenv("PROXMOX_STATS_URL")
    PROXMOX_STATS_BASE_URL: str = (
        os.getenv("PROXMOX_STATS_BASE_URL") or PROXMOX_STATS_URL
    )
    PROXMOX_STATS_TIMEOUT_SECONDS: float = float(
        os.getenv("PROXMOX_STATS_TIMEOUT_SECONDS", "2.5")
    )
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://192.168.50.201:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    OLLAMA_TIMEOUT_S: int = int(os.getenv("OLLAMA_TIMEOUT_S", "30"))
    OPS_CORE_CHECK_IDS: tuple[str, ...] = tuple(
        check_id.strip()
        for check_id in os.getenv("OPS_CORE_CHECK_IDS", "").split(",")
        if check_id.strip()
    )
    MONITOR_INTERVAL: int = int(os.getenv("MONITOR_INTERVAL", 30))
    OPSMONITOR_DB_PATH: str = os.getenv(
        "OPSMONITOR_DB_PATH", "/opt/ops-monitor/data/ops-monitor.sqlite3"
    )


settings = Settings()
