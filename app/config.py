import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PORTAINER_BASE_URL: str = os.getenv("PORTAINER_BASE_URL")
    PORTAINER_API_KEY: str = os.getenv("PORTAINER_API_KEY")
    NTFY_URL: str = os.getenv("NTFY_URL")
    NTFY_TOPIC: str = os.getenv("NTFY_TOPIC")
    PROXMOX_STATS_URL: str = os.getenv("PROXMOX_STATS_URL")
    MONITOR_INTERVAL: int = int(os.getenv("MONITOR_INTERVAL", 30))

settings = Settings()
