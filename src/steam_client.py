import json
import os
import re
import time
from pathlib import Path

import requests

import cache

STEAM_ID64_RE = re.compile(r"^\d{17}$")
LOGIN_USER_BLOCK_RE = re.compile(r'"(\d{17})"\s*\{(.*?)\n\t\}', re.DOTALL)

RESOLVE_VANITY_URL = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
GET_OWNED_GAMES_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"
STORE_ITEMS_URL = "https://api.steampowered.com/IStoreBrowseService/GetItems/v1/"

# O appdetails aceita 1 appid por chamada e corta em ~200 chamadas/5min, o que
# levava ~10min para montar um grafo de ~900 jogos. Este endpoint aceita 200
# appids por chamada (400 acima disso) e responde em ~0.5s, então o mesmo
# grafo sai em segundos.
STORE_ITEMS_BATCH = 200
TAGS_PER_GAME = 20
STORE_SEARCH_URL = "https://store.steampowered.com/search/results/"
LOGO_APPID_RE = re.compile(r"/apps/(\d+)/")

# Gêneros oficiais da Steam: é o subconjunto das tags que a busca da loja
# aceita no parâmetro `genre` (categories como "Multi-player" não servem).
STEAM_GENRES = frozenset(
    {
        "Action",
        "Adventure",
        "Casual",
        "Free To Play",
        "Indie",
        "Massively Multiplayer",
        "RPG",
        "Racing",
        "Simulation",
        "Sports",
        "Strategy",
    }
)

# Gêneros que descrevem o jogo mas a busca da loja não aceita como filtro.
EXTRA_GENRES = frozenset({"Early Access", "Gore", "Nudity", "Sexual Content", "Violent"})

# appdetails devolve em `categories` tanto modo de jogo (Co-op, PvP) quanto
# recurso de plataforma (Steam Cloud, Remote Play, opções de acessibilidade).
# Só o primeiro grupo diz se dois jogos são parecidos: sem esse filtro, um
# FPS competitivo "combina" com um jogo casual por ambos terem Stereo Sound.
GAMEPLAY_CATEGORIES = frozenset(
    {
        "Co-op",
        "Cross-Platform Multiplayer",
        "Includes level editor",
        "LAN Co-op",
        "LAN PvP",
        "MMO",
        "Multi-player",
        "Online Co-op",
        "Online PvP",
        "PvP",
        "Remote Play Together",
        "Shared/Split Screen",
        "Shared/Split Screen Co-op",
        "Shared/Split Screen PvP",
        "Single-player",
        "Steam Workshop",
        "VR Only",
        "VR Supported",
    }
)

MEANINGFUL_TAGS = STEAM_GENRES | EXTRA_GENRES | GAMEPLAY_CATEGORIES

# Ordenações que a busca da loja aceita, expostas no menu do CLI.
STORE_SORTS = {
    "mais vendidos": {"filter": "globaltopsellers"},
    "melhor avaliados": {"sort_by": "Reviews_DESC"},
    "lançamentos recentes": {"sort_by": "Released_DESC"},
    "mais baratos": {"sort_by": "Price_ASC"},
}

# A busca devolve no máximo 100 itens por chamada; acima disso, pagina-se
# com `start`.
SEARCH_PAGE_SIZE = 100

# O appdetails corta em ~200 chamadas/5min (medido: HTTP 429 na 111a chamada
# em 34s). 1.5s entre chamadas mantém o ritmo abaixo do limite.
APP_DETAILS_INTERVAL = 1.5
_last_app_details_call = 0.0


class SteamProfileError(Exception):
    pass


def _steam_install_dirs():
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            yield Path(winreg.QueryValueEx(key, "SteamPath")[0])
    except (ImportError, OSError):
        pass

    yield Path(r"C:\Program Files (x86)\Steam")
    yield Path.home() / ".steam" / "steam"
    yield Path.home() / "Library" / "Application Support" / "Steam"


def detect_local_steam_account() -> tuple[str, str] | None:
    """Lê a conta Steam logada nesta máquina, sem precisar o usuário digitar.

    Devolve (steamid64, persona_name) da conta usada mais recentemente, lendo
    config/loginusers.vdf da instalação local; None se o Steam não estiver
    instalado ou nenhuma conta tiver feito login. Não depende do cliente estar
    aberto no momento.
    """
    for steam_dir in _steam_install_dirs():
        config = steam_dir / "config" / "loginusers.vdf"
        if not config.is_file():
            continue

        accounts = []
        for steam_id, block in LOGIN_USER_BLOCK_RE.findall(config.read_text(encoding="utf-8", errors="ignore")):
            fields = dict(re.findall(r'"(\w+)"\s*"([^"]*)"', block))
            accounts.append(
                (
                    fields.get("MostRecent") == "1",
                    int(fields.get("Timestamp", 0)),
                    steam_id,
                    fields.get("PersonaName", ""),
                )
            )

        if accounts:
            _, _, steam_id, persona = max(accounts)
            return steam_id, persona

    return None


def resolve_steam_id(user_input: str, api_key: str | None = None) -> str:
    """Recebe um SteamID64 ou uma vanity URL/nome e devolve o SteamID64."""
    user_input = user_input.strip()

    vanity = _extract_vanity(user_input)
    if vanity is None and STEAM_ID64_RE.match(user_input):
        return user_input

    vanity = vanity or user_input
    api_key = api_key or os.getenv("STEAM_API_KEY")
    if not api_key:
        raise SteamProfileError("STEAM_API_KEY não configurada no .env.")

    try:
        response = requests.get(
            RESOLVE_VANITY_URL,
            params={"key": api_key, "vanityurl": vanity},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SteamProfileError(f"Falha ao conectar na API da Steam: {exc}") from exc

    data = response.json().get("response", {})
    if data.get("success") != 1:
        raise SteamProfileError(
            f"Perfil '{user_input}' não encontrado. Confira o SteamID ou a vanity URL."
        )

    return data["steamid"]


def _extract_vanity(user_input: str) -> str | None:
    match = re.search(r"steamcommunity\.com/id/([^/]+)", user_input)
    if match:
        return match.group(1)
    return None


def get_owned_games(steam_id: str, api_key: str | None = None) -> list[dict]:
    """Busca a biblioteca de jogos do usuário, ordenada por tempo jogado (desc)."""
    api_key = api_key or os.getenv("STEAM_API_KEY")
    if not api_key:
        raise SteamProfileError("STEAM_API_KEY não configurada no .env.")

    try:
        response = requests.get(
            GET_OWNED_GAMES_URL,
            params={
                "key": api_key,
                "steamid": steam_id,
                "include_appinfo": 1,
                "include_played_free_games": 1,
                "format": "json",
            },
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SteamProfileError(f"Falha ao conectar na API da Steam: {exc}") from exc

    games = response.json().get("response", {}).get("games")
    if not games:
        raise SteamProfileError(
            "Nenhum jogo encontrado. O perfil pode estar privado "
            "(Configurações -> Privacidade -> Detalhes do jogo) ou a biblioteca está vazia."
        )

    return sorted(games, key=lambda game: game.get("playtime_forever", 0), reverse=True)


def get_store_candidates(
    genres: set[str] | None = None,
    count: int = 1000,
    sort: str = "mais vendidos",
) -> list[dict]:
    """Busca jogos da loja Steam para servir de catálogo externo à biblioteca.

    Filtra pelos gêneros do jogo de origem para o pool ficar relevante, e
    ordena conforme `sort` (ver STORE_SORTS). Puxar o catálogo completo
    (~200k apps) é inviável pelo rate limit do appdetails, então o pool para
    em `count` jogos, divididos entre os gêneros do jogo de origem.
    """
    sort_params = STORE_SORTS[sort]
    searches = sorted(genres & STEAM_GENRES) if genres else []
    per_search = max(count // len(searches), SEARCH_PAGE_SIZE) if searches else count

    candidates = {}
    for genre in searches or [None]:
        for start in range(0, per_search, SEARCH_PAGE_SIZE):
            params = {
                "json": 1,
                "start": start,
                "count": SEARCH_PAGE_SIZE,
                "category1": 998,
                "l": "english",
                **sort_params,
            }
            if genre:
                params["genre"] = genre

            try:
                response = requests.get(STORE_SEARCH_URL, params=params, timeout=15)
                response.raise_for_status()
            except requests.RequestException as exc:
                raise SteamProfileError(
                    f"Falha ao buscar catálogo da loja Steam: {exc}"
                ) from exc

            items = response.json().get("items", [])
            for item in items:
                match = LOGO_APPID_RE.search(item.get("logo", ""))
                if match:
                    appid = int(match.group(1))
                    candidates[appid] = {"appid": appid, "name": item["name"]}

            if len(items) < SEARCH_PAGE_SIZE:
                break

    return list(candidates.values())


def get_apps_tags(appids: list[int]) -> dict[int, set[int]]:
    """Busca as tags de vários jogos de uma vez, para o cálculo de similaridade.

    Devolve {appid: set de tagids}. São as tags de usuário da loja (FPS,
    Souls-like, Co-op...), sinal bem melhor que os `genres`/`categories` do
    appdetails, onde recurso de plataforma ("Stereo Sound") se misturava com
    gênero e poluía o Jaccard. Os ids são usados crus: para comparar conjuntos
    o nome da tag não importa.

    Appid sem retorno (jogo removido da loja, playtest, DLC) fica com set
    vazio, sem travar o pipeline.
    """
    tags = {}
    faltando = []
    for appid in appids:
        cached = cache.get(_tags_key(appid))
        if cached is None:
            faltando.append(appid)
        else:
            tags[appid] = set(cached)

    for start in range(0, len(faltando), STORE_ITEMS_BATCH):
        lote = faltando[start : start + STORE_ITEMS_BATCH]
        payload = {
            "ids": [{"appid": appid} for appid in lote],
            "context": {
                "language": "english",
                "country_code": "BR",
                "steam_realm": 1,
            },
            "data_request": {"include_tag_count": TAGS_PER_GAME},
        }

        try:
            response = requests.get(
                STORE_ITEMS_URL, params={"input_json": json.dumps(payload)}, timeout=30
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SteamProfileError(f"Falha ao buscar tags na loja Steam: {exc}") from exc

        recebidos = {}
        for item in response.json().get("response", {}).get("store_items", []):
            appid = item.get("id")
            if appid is not None:
                recebidos[appid] = {t["tagid"] for t in item.get("tags", [])}

        for appid in lote:
            tags[appid] = recebidos.get(appid, set())
            cache.set(_tags_key(appid), sorted(tags[appid]))
        cache.flush()

    return tags


def _tags_key(appid: int) -> str:
    """Chave separada no cache: as entradas antigas guardam nomes de
    genres/categories do appdetails, incompatíveis com os tagids daqui."""
    return f"tags_v2_{appid}"


def _get_app_details(appid: int, retries: int = 3) -> requests.Response:
    """Chama o appdetails respeitando o rate limit, com backoff no HTTP 429."""
    global _last_app_details_call

    for attempt in range(retries):
        wait = APP_DETAILS_INTERVAL - (time.monotonic() - _last_app_details_call)
        if wait > 0:
            time.sleep(wait)

        response = requests.get(APP_DETAILS_URL, params={"appids": appid}, timeout=10)
        _last_app_details_call = time.monotonic()

        if response.status_code != 429:
            response.raise_for_status()
            return response

        pausa = 30 * (attempt + 1)
        print(f"Rate limit da Steam atingido; aguardando {pausa}s...")
        time.sleep(pausa)

    raise requests.RequestException(f"appid {appid}: rate limit persistente")


def get_app_tags(appid: int) -> set[str]:
    """Busca gêneros e categorias de um jogo na Steam Store e devolve como set de tags.

    Só volta o que é MEANINGFUL_TAGS (gênero e modo de jogo); recurso de
    plataforma e acessibilidade fica de fora para não poluir o Jaccard.

    Devolve um set vazio (em vez de lançar) quando o appid não tem dados na
    loja (jogo removido, DLC, software), pois isso não deve travar o pipeline
    de similaridade — só esse jogo fica sem tags.

    O cache em /data/cache.json guarda a resposta crua da loja, e o filtro é
    aplicado na leitura: mudar MEANINGFUL_TAGS não exige invalidar o cache.
    """
    cached = cache.get(appid)
    if cached is not None:
        return set(cached) & MEANINGFUL_TAGS

    try:
        response = _get_app_details(appid)
    except requests.RequestException as exc:
        print(f"Aviso: falha ao buscar detalhes do appid {appid}: {exc}")
        return set()

    payload = response.json().get(str(appid), {})
    if not payload.get("success"):
        print(f"Aviso: appid {appid} sem dados na loja Steam (ignorado).")
        cache.set(appid, [])
        cache.flush()
        return set()

    data = payload.get("data", {})
    genres = {g["description"] for g in data.get("genres", [])}
    categories = {c["description"] for c in data.get("categories", [])}
    tags = genres | categories
    cache.set(appid, sorted(tags))
    cache.flush()
    return tags & MEANINGFUL_TAGS
