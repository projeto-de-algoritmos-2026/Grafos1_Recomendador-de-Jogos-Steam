import webbrowser

from dotenv import load_dotenv

from graph import build_graph, dijkstra
from steam_client import (
    STEAM_GENRES,
    SteamProfileError,
    detect_local_steam_account,
    get_app_tags,
    get_owned_games,
    get_store_candidates,
    resolve_steam_id,
)

STORE_URL = "https://store.steampowered.com/app/{appid}"

PUBLIC_PROFILE_WARNING = (
    "Aviso: seu perfil Steam precisa estar público "
    "(Configurações -> Privacidade -> Detalhes do jogo), "
    "senão a busca da biblioteca retorna vazia."
)


def prompt_steam_id() -> str:
    print(PUBLIC_PROFILE_WARNING)

    detected = detect_local_steam_account()
    if detected:
        steam_id, persona = detected
        user_input = input(
            f"Conta detectada no PC: {persona} ({steam_id}). "
            "Enter para usar, ou digite outro SteamID64/vanity URL: "
        ).strip()
        if not user_input:
            return steam_id
    else:
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


def build_recommendations(
    games: list[dict], candidates: list[dict], source_appid: int, n: int
) -> list[dict]:
    """Roda Dijkstra do jogo de origem e devolve os N jogos novos mais próximos.

    O grafo cobre biblioteca + catálogo da loja, mas só entram na resposta os
    jogos que o usuário ainda não tem: o caminho pode passar por jogos da
    biblioteca (é isso que dá sentido ao Dijkstra em vez de só olhar o
    vizinho direto), mas o destino recomendado é sempre novo.
    """
    owned = {game["appid"] for game in games}
    nodes = games + candidates

    games_tags = {node["appid"]: get_app_tags(node["appid"]) for node in nodes}
    adjacency = build_graph(games_tags)
    distances = dijkstra(adjacency, source_appid)

    names_by_appid = {node["appid"]: node["name"] for node in nodes}
    ranked = sorted(
        (
            (appid, dist)
            for appid, dist in distances.items()
            if appid not in owned
        ),
        key=lambda item: item[1],
    )

    return [
        {"appid": appid, "name": names_by_appid[appid], "distance": dist}
        for appid, dist in ranked[:n]
    ]


def print_recommendations(recommendations: list[dict]) -> list[str]:
    """Exibe as recomendações (nome, distância e link da loja) e devolve os links."""
    if not recommendations:
        print("Nenhum jogo próximo o suficiente foi encontrado.")
        return []

    links = []
    for index, rec in enumerate(recommendations, start=1):
        link = STORE_URL.format(appid=rec["appid"])
        links.append(link)
        print(f"{index}. {rec['name']} (distância: {rec['distance']:.3f}) - {link}")

    return links


def prompt_open_browser(links: list[str]) -> None:
    """Pergunta se o usuário quer abrir as recomendações no navegador padrão.

    Abre uma aba por jogo. O cliente Steam não serve aqui: nenhuma URI
    steam:// abre janela nova — todas reaproveitam a view atual, então os
    N jogos acabariam sobrescrevendo uns aos outros na mesma janela.
    """
    if not links:
        return
    answer = input("Abrir as recomendações no navegador? (s/N): ").strip().lower()
    if answer == "s":
        for link in links:
            webbrowser.open_new_tab(link)


def main():
    load_dotenv()
    steam_id = prompt_steam_id()
    print(f"SteamID64 resolvido: {steam_id}")
    games = print_owned_games(steam_id)
    source_appid = prompt_source_game(games)
    print(f"Jogo de origem escolhido: appid {source_appid}")

    owned = {game["appid"] for game in games}
    source_genres = get_app_tags(source_appid) & STEAM_GENRES
    candidates = [
        c for c in get_store_candidates(source_genres) if c["appid"] not in owned
    ]
    print(
        f"Catálogo da loja ({', '.join(sorted(source_genres)) or 'geral'}): "
        f"{len(candidates)} jogos que você ainda não tem."
    )

    n = prompt_num_recommendations(len(candidates))
    print(f"Número de recomendações: {n}")
    print("Buscando gêneros e categorias (pode demorar na primeira vez)...")

    recommendations = build_recommendations(games, candidates, source_appid, n)
    links = print_recommendations(recommendations)
    prompt_open_browser(links)


if __name__ == "__main__":
    main()
