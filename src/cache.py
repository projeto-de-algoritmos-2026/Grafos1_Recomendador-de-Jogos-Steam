import json
import os
import time

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cache.json")
DEFAULT_TTL_DAYS = 30

_entries: dict | None = None
_dirty = False


def _load() -> dict:
    """Carrega o cache do disco uma vez e mantém em memória.

    Reler o arquivo a cada consulta fazia o custo virar quadrático: com ~900
    jogos, montar o grafo reparseava o JSON inteiro 900 vezes, deixando lento
    até o caso em que nada é buscado na Steam.
    """
    global _entries
    if _entries is None:
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                _entries = json.load(f)
        except (OSError, json.JSONDecodeError):
            _entries = {}
    return _entries


def flush() -> None:
    """Grava o cache trocando o arquivo por um temporário já completo.

    os.replace é atômico, então uma interrupção no meio da escrita não deixa
    o cache truncado. No Windows ele falha com "acesso negado" se antivírus ou
    indexador ainda estiver com o arquivo aberto, daí as tentativas.
    """
    global _dirty
    if not _dirty:
        return

    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    tmp_path = f"{CACHE_PATH}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(_load(), f, ensure_ascii=False, indent=2)

    for tentativa in range(5):
        try:
            os.replace(tmp_path, CACHE_PATH)
            _dirty = False
            return
        except PermissionError:
            time.sleep(0.2 * (tentativa + 1))

    print("Aviso: nao foi possivel gravar o cache local (arquivo em uso).")


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
    """Grava só em memória; chame flush() para persistir em disco."""
    global _dirty
    _load()[str(appid)] = {"timestamp": time.time(), "value": value}
    _dirty = True


def is_cached(appid: int, ttl_days: int = DEFAULT_TTL_DAYS) -> bool:
    """Se o appid já está em cache — usado para prever quantas consultas à
    Steam a montagem do grafo ainda vai custar."""
    return get(appid, ttl_days) is not None
