def jaccard(tags_a: set[str], tags_b: set[str]) -> float:
    """Jaccard(A, B) = |A intersecao B| / |A uniao B|. 0 se ambos vazios."""
    union = tags_a | tags_b
    if not union:
        return 0.0
    return len(tags_a & tags_b) / len(union)
