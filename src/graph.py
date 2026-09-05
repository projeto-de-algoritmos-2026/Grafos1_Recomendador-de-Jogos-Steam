from similarity import jaccard

DEFAULT_THRESHOLD = 0.1


def build_graph(
    games_tags: dict[int, set[str]], threshold: float = DEFAULT_THRESHOLD
) -> dict[int, list[tuple[int, float]]]:
    """Constroi grafo ponderado só sobre a biblioteca do usuário (issue #10).

    Nós = appids em games_tags. Aresta (a, b) existe se jaccard(tags_a, tags_b)
    > threshold, com peso = 1 - jaccard (peso baixo = jogos parecidos, o que
    o Dijkstra prioriza). Threshold evita grafo quase completo, já que
    qualquer par de jogos costuma compartilhar alguma tag.
    """
    appids = list(games_tags)
    adjacency: dict[int, list[tuple[int, float]]] = {appid: [] for appid in appids}

    for i, appid_a in enumerate(appids):
        for appid_b in appids[i + 1 :]:
            sim = jaccard(games_tags[appid_a], games_tags[appid_b])
            if sim > threshold:
                weight = 1 - sim
                adjacency[appid_a].append((appid_b, weight))
                adjacency[appid_b].append((appid_a, weight))

    return adjacency
