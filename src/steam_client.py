import os
import re
from pathlib import Path

import requests

import cache

STEAM_ID64_RE = re.compile(r"^\d{17}$")
LOGIN_USER_BLOCK_RE = re.compile(r'"(\d{17})"\s*\{(.*?)\n\t\}', re.DOTALL)

RESOLVE_VANITY_URL = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
GET_OWNED_GAMES_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"
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


def get_store_candidates(genres: set[str] | None = None, count: int = 90) -> list[dict]:
    """Busca jogos da loja Steam para servir de catálogo externo à biblioteca.

    Filtra por gênero (os do jogo de origem) para o pool ficar relevante, e
    ordena por mais vendidos: ordenar por avaliação enche o pool de indies
    nichados de review alta, que não são recomendação útil. Puxar o catálogo
    completo (~200k apps) é inviável pelo rate limit do appdetails, então o
    pool é limitado a `count` jogos.
    """
    searches = sorted(genres & STEAM_GENRES) if genres else []
    per_search = max(count // len(searches), 10) if searches else count

    candidates = {}
    for genre in searches or [None]:
        params = {
            "json": 1,
            "count": per_search,
            "category1": 998,
            "filter": "globaltopsellers",
            "l": "english",
        }
        if genre:
            params["genre"] = genre

        try:
            response = requests.get(STORE_SEARCH_URL, params=params, timeout=15)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SteamProfileError(f"Falha ao buscar catálogo da loja Steam: {exc}") from exc

        for item in response.json().get("items", []):
            match = LOGO_APPID_RE.search(item.get("logo", ""))
            if match:
                appid = int(match.group(1))
                candidates[appid] = {"appid": appid, "name": item["name"]}

    return list(candidates.values())


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
        response = requests.get(
            APP_DETAILS_URL,
            params={"appids": appid},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Aviso: falha ao buscar detalhes do appid {appid}: {exc}")
        return set()

    payload = response.json().get(str(appid), {})
    if not payload.get("success"):
        print(f"Aviso: appid {appid} sem dados na loja Steam (ignorado).")
        cache.set(appid, [])
        return set()

    data = payload.get("data", {})
    genres = {g["description"] for g in data.get("genres", [])}
    categories = {c["description"] for c in data.get("categories", [])}
    tags = genres | categories
    cache.set(appid, sorted(tags))
    return tags & MEANINGFUL_TAGS
