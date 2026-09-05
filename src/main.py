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


def prompt_source_game(games: list[dict]) -> int:
    """Pede o número do jogo (na lista já exibida) e devolve o appid escolhido."""
    while True:
        raw = input("Escolha o número do jogo de origem: ")
        if not raw.isdigit():
            print("Entrada inválida. Digite um número.")
            continue

        index = int(raw)
        if not (1 <= index <= len(games)):
            print(f"Escolha um número entre 1 e {len(games)}.")
            continue

        return games[index - 1]["appid"]


def prompt_num_recommendations(available_games: int, default: int = 5) -> int:
    """Pede quantas recomendações (N) o usuário quer, com valor padrão e limite."""
    while True:
        raw = input(f"Quantas recomendações você quer? (padrão: {default}): ").strip()
        if raw == "":
            n = default
        elif raw.isdigit() and int(raw) > 0:
            n = int(raw)
        else:
            print("Entrada inválida. Digite um número inteiro positivo.")
            continue

        if n > available_games:
            print(
                f"Só há {available_games} jogos disponíveis; ajustando N para {available_games}."
            )
            n = available_games

        return n


def main():
    load_dotenv()
    steam_id = prompt_steam_id()
    print(f"SteamID64 resolvido: {steam_id}")
    games = print_owned_games(steam_id)
    source_appid = prompt_source_game(games)
    print(f"Jogo de origem escolhido: appid {source_appid}")
    n = prompt_num_recommendations(len(games))
    print(f"Número de recomendações: {n}")


if __name__ == "__main__":
    main()
