import hashlib
import os
from typing import Protocol

from vigia.text import tokenize


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        pass


class HashingEmbedder:
    dim = 128
    min_cosine = 0.72

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_vector(texto, self.dim) for texto in texts]


class FastEmbedEmbedder:
    min_cosine = 0.5

    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)
        self.dim = len(next(self._model.embed(["vigia"])).tolist())

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(texts)]


class VertexEmbedder:
    def __init__(self) -> None:
        self.model = os.environ.get("VIGIA_VERTEX_EMBED_MODEL", "text-embedding-004")
        self.dim = int(os.environ.get("VIGIA_EMBED_DIM", "768"))

    def embed(self, texts: list[str]) -> list[list[float]]:
        from google import genai

        client = genai.Client(
            vertexai=True,
            project=os.environ["GOOGLE_CLOUD_PROJECT"],
            location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )
        response = client.models.embed_content(model=self.model, contents=texts)
        vectors = [list(item.values) for item in response.embeddings]
        if vectors:
            self.dim = len(vectors[0])
        return vectors


_MODELO_LEVE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_fastembed_cache: FastEmbedEmbedder | None = None


def make_embedder() -> Embedder:
    kind = os.environ.get("VIGIA_EMBEDDER", "auto")
    if kind == "hash":
        return HashingEmbedder()
    if kind == "vertex":
        return VertexEmbedder()
    if kind in {"auto", "fastembed"}:
        try:
            return _fastembed()
        except Exception:
            if kind == "fastembed":
                raise
            return HashingEmbedder()
    raise ValueError(f"embedder desconhecido: {kind}")


def _fastembed() -> FastEmbedEmbedder:
    global _fastembed_cache
    if _fastembed_cache is None:
        nome = os.environ.get("VIGIA_EMBED_MODEL", _MODELO_LEVE)
        _fastembed_cache = FastEmbedEmbedder(nome)
    return _fastembed_cache


def _vector(texto: str, dim: int) -> list[float]:
    values = [0.0] * dim
    for token in tokenize(texto):
        digest = hashlib.sha256(token.encode()).digest()
        values[int.from_bytes(digest[:4], "big") % dim] += 1.0
    norm = sum(value * value for value in values) ** 0.5 or 1.0
    return [value / norm for value in values]
