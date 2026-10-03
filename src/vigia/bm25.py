import math
from collections import Counter

from vigia.text import tokenize


def build_stats(docs: list[list[str]]) -> tuple[dict[str, int], dict[str, float], float]:
    df: dict[str, int] = {}
    total = 0
    for tokens in docs:
        total += len(tokens)
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1
    n = len(docs) or 1
    vocab = {term: index for index, term in enumerate(sorted(df))}
    idf = {
        term: math.log(1 + (n - freq + 0.5) / (freq + 0.5))
        for term, freq in df.items()
    }
    avgdl = (total / n) if docs else 0.0
    return vocab, idf, avgdl


def sparse_document(
    tokens: list[str],
    vocab: dict[str, int],
    idf: dict[str, float],
    avgdl: float,
    k1: float = 1.5,
    b: float = 0.75,
) -> tuple[list[int], list[float]]:
    if not tokens or avgdl <= 0:
        return [], []
    tf = Counter(tokens)
    dl = len(tokens)
    indices: list[int] = []
    values: list[float] = []
    for term, freq in tf.items():
        if term not in vocab:
            continue
        saturation = (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * dl / avgdl))
        indices.append(vocab[term])
        values.append(idf[term] * saturation)
    return indices, values


def sparse_query(texto: str, vocab: dict[str, int]) -> tuple[list[int], list[float]]:
    indices: list[int] = []
    values: list[float] = []
    seen: set[str] = set()
    for term in tokenize(texto):
        if term in vocab and term not in seen:
            seen.add(term)
            indices.append(vocab[term])
            values.append(1.0)
    return indices, values
