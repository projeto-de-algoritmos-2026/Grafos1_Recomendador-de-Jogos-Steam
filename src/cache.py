import json
import os
import time

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cache.json")
DEFAULT_TTL_DAYS = 30


def _load() -> dict:
    if not os.path.exists(CACHE_PATH):
        return {}
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(cache: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def get(appid: int, ttl_days: int = DEFAULT_TTL_DAYS):
    """Devolve o valor em cache para o appid, ou None se ausente/expirado."""
    entry = _load().get(str(appid))
    if entry is None:
        return None

    age_days = (time.time() - entry["timestamp"]) / 86400
    if age_days > ttl_days:
        return None

    return entry["value"]


def set(appid: int, value) -> None:
    cache = _load()
    cache[str(appid)] = {"timestamp": time.time(), "value": value}
    _save(cache)
