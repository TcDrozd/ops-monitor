from __future__ import annotations

from pathlib import Path
import yaml
from app.models import Registry

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "checks.yml"

if not REGISTRY_PATH.exists():
    raise RuntimeError(
        "checks.yml missing. Copy checks.example.yml to checks.yml and configure it."
    )

def load_registry(path: Path = REGISTRY_PATH) -> Registry:
    if not path.exists():
        raise FileNotFoundError(f"Missing checks.yml at {path}")

    data = yaml.safe_load(path.read_text()) or {}
    reg = Registry.model_validate(data)

    # Ensure unique IDs
    seen = set()
    for c in reg.checks:
        if c.id in seen:
            raise ValueError(f"Duplicate check id: {c.id}")
        seen.add(c.id)

    return reg

def apply_defaults(reg: Registry) -> dict[str, dict]:
    """
    Produce a normalized dict keyed by check id with defaults applied.
    Returns pure python dicts so they serialize cleanly.
    """
    out: dict[str, dict] = {}
    d = reg.defaults

    for c in reg.checks:
        cd = c.model_dump()
        cd["interval_s"] = cd["interval_s"] or d.interval_s
        cd["timeout_s"] = cd["timeout_s"] or d.timeout_s
        cd["retries"] = cd["retries"] or d.retries
        out[c.id] = cd

    return out
