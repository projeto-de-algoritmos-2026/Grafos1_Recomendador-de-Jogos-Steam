import os
import re

import requests

STEAM_ID64_RE = re.compile(r"^\d{17}$")

RESOLVE_VANITY_URL = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
GET_OWNED_GAMES_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"


class SteamProfileError(Exception):
    pass


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
