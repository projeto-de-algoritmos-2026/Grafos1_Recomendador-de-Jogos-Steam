from dotenv import load_dotenv

from steam_client import SteamProfileError, get_owned_games, resolve_steam_id

PUBLIC_PROFILE_WARNING = (
    "Aviso: seu perfil Steam precisa estar público "
    "(Configurações -> Privacidade -> Detalhes do jogo), "
    "senão a busca da biblioteca retorna vazia."
)


def prompt_steam_id() -> str:
    print(PUBLIC_PROFILE_WARNING)
    user_input = input("Informe seu SteamID64 ou vanity URL: ")
    try:
        return resolve_steam_id(user_input)
    except SteamProfileError as exc:
        print(f"Erro: {exc}")
        raise SystemExit(1)


def print_owned_games(steam_id: str) -> list[dict]:
    try:
        games = get_owned_games(steam_id)
    except SteamProfileError as exc:
        print(f"Erro: {exc}")
        raise SystemExit(1)

    for index, game in enumerate(games, start=1):
        hours = game.get("playtime_forever", 0) / 60
        print(f"{index}. {game['name']} ({hours:.1f}h)")

    return games


def main():
    load_dotenv()
    steam_id = prompt_steam_id()
    print(f"SteamID64 resolvido: {steam_id}")
    print_owned_games(steam_id)


if __name__ == "__main__":
    main()
