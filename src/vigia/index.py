import json
from datetime import datetime, timezone
from pathlib import Path

from qdrant_client import QdrantClient, models

from vigia.bm25 import build_stats, sparse_document, sparse_query
from vigia.embeddings import Embedder
from vigia.errors import IndiceIndisponivel
from vigia.fusion import rrf
from vigia.models import Chunk, Citacao
from vigia.text import tokenize

COLLECTION = "vigia"
_CANDIDATES = 20
_INDEX_ERRORS = (ConnectionError, TimeoutError, OSError)


class Index:
    def __init__(
        self,
        client: QdrantClient,
        embedder: Embedder,
        vocab_path: Path | None = None,
        collection: str = COLLECTION,
    ) -> None:
        self.client = client
        self.embedder = embedder
        self.vocab_path = vocab_path
        self.collection = collection
        self.vocab: dict[str, int] = {}
        self.min_cosine = float(getattr(embedder, "min_cosine", 0.72))
        self._load_vocab()

    def rebuild(self, chunks: list[Chunk]) -> None:
        tokenized = [tokenize(chunk.texto) for chunk in chunks]
        vocab, idf, avgdl = build_stats(tokenized)
        self.vocab = vocab
        self._save_vocab()
        self._reset_collection()
        points = []
        vectors = self.embedder.embed([chunk.texto for chunk in chunks]) if chunks else []
        for chunk, tokens, dense in zip(chunks, tokenized, vectors, strict=True):
            indices, values = sparse_document(tokens, vocab, idf, avgdl)
            if not indices:
                continue
            points.append(_point(chunk, dense, indices, values))
        if points:
            self._call(lambda: self.client.upsert(collection_name=self.collection, points=points))

    def search(
        self,
        consulta: str,
        k: int,
        tipo: str | None,
        incluir_expirados: bool,
        now: datetime | None = None,
    ) -> list[Citacao]:
        self._load_vocab()
        if not self.vocab or not tokenize(consulta):
            return []
        filtro = _filtro(tipo, incluir_expirados, now or datetime.now(timezone.utc))
        dense_vector = self.embedder.embed([consulta])[0]
        dense = self._call(
            lambda: self.client.query_points(
                collection_name=self.collection,
                query=dense_vector,
                using="dense",
                query_filter=filtro,
                limit=_CANDIDATES,
            )
        )
        indices, values = sparse_query(consulta, self.vocab)
        sparse_points = []
        if indices:
            sparse = self._call(
                lambda: self.client.query_points(
                    collection_name=self.collection,
                    query=models.SparseVector(indices=indices, values=values),
                    using="bm25",
                    query_filter=filtro,
                    limit=_CANDIDATES,
                )
            )
            sparse_points = sparse.points
        payloads = {}
        dense_scores: dict[str, float] = {}
        dense_ids = []
        sparse_ids = []
        for point in dense.points:
            chunk_id = point.payload["chunk_id"]
            payloads[chunk_id] = point.payload
            dense_scores[chunk_id] = float(point.score)
            dense_ids.append(chunk_id)
        for point in sparse_points:
            chunk_id = point.payload["chunk_id"]
            payloads[chunk_id] = point.payload
            sparse_ids.append(chunk_id)
        query_terms = set(tokenize(consulta))
        chosen = []
        seen: set[tuple[str, str]] = set()
        for chunk_id in rrf([dense_ids, sparse_ids]):
            payload = payloads[chunk_id]
            if not _relevante(query_terms, payload, dense_scores.get(chunk_id, 0.0), self.min_cosine):
                continue
            key = (payload["doc_id"], payload["secao"])
            if key in seen:
                continue
            seen.add(key)
            chosen.append(_citacao(payload))
            if len(chosen) == k:
                break
        return chosen

    def trecho(self, chunk_id: str) -> Citacao | None:
        records = self._scroll("chunk_id", chunk_id)
        if not records:
            return None
        return _citacao(records[0].payload)

    def documento(self, doc_id: str) -> dict | None:
        records = self._scroll("doc_id", doc_id)
        if not records:
            return None
        payload = records[0].payload
        return {
            "doc_id": payload["doc_id"],
            "titulo": payload["titulo"],
            "tipo": payload["tipo"],
            "vigencia_inicio": payload["vigencia_inicio"],
            "vigencia_fim": payload["vigencia_fim"],
        }

    def _scroll(self, key: str, value: str) -> list:
        found, _offset = self._call(
            lambda: self.client.scroll(
                collection_name=self.collection,
                scroll_filter=models.Filter(
                    must=[models.FieldCondition(key=key, match=models.MatchValue(value=value))]
                ),
                limit=1,
            )
        )
        return found

    def _reset_collection(self) -> None:
        def reset() -> None:
            if self.client.collection_exists(self.collection):
                self.client.delete_collection(self.collection)
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config={
                    "dense": models.VectorParams(
                        size=self.embedder.dim,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={"bm25": models.SparseVectorParams()},
            )

        self._call(reset)

    def _call(self, fn):
        try:
            return fn()
        except _INDEX_ERRORS as exc:
            raise IndiceIndisponivel("indice indisponivel") from exc

    def _load_vocab(self) -> None:
        if self.vocab or self.vocab_path is None or not self.vocab_path.exists():
            return
        self.vocab = {term: int(index) for term, index in json.loads(self.vocab_path.read_text()).items()}

    def _save_vocab(self) -> None:
        if self.vocab_path is None:
            return
        self.vocab_path.parent.mkdir(parents=True, exist_ok=True)
        self.vocab_path.write_text(json.dumps(self.vocab, ensure_ascii=False))


def _point(chunk: Chunk, dense: list[float], indices: list[int], values: list[float]):
    import uuid

    return models.PointStruct(
        id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.id)),
        vector={
            "dense": dense,
            "bm25": models.SparseVector(indices=indices, values=values),
        },
        payload={
            "chunk_id": chunk.id,
            "doc_id": chunk.doc_id,
            "titulo": chunk.titulo,
            "tipo": chunk.tipo,
            "secao": chunk.secao,
            "texto": chunk.texto,
            "parent_texto": chunk.parent_texto,
            "vigencia_inicio": chunk.vigencia_inicio,
            "vigencia_fim": chunk.vigencia_fim,
            "vigencia_inicio_ts": _ts(chunk.vigencia_inicio, end=False),
            "vigencia_fim_ts": _ts(chunk.vigencia_fim, end=True),
        },
    )


def _citacao(payload: dict) -> Citacao:
    return Citacao(
        chunk_id=payload["chunk_id"],
        doc_id=payload["doc_id"],
        titulo=payload["titulo"],
        tipo=payload["tipo"],
        secao=payload["secao"],
        texto=payload["parent_texto"] or payload["texto"],
        vigencia_fim=payload["vigencia_fim"],
    )


def _ts(iso_date: str, end: bool) -> int:
    day = datetime.fromisoformat(iso_date)
    if end:
        moment = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc)
    else:
        moment = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return int(moment.timestamp())


def _relevante(query_terms: set[str], payload: dict, dense_score: float, min_cosine: float) -> bool:
    if dense_score >= min_cosine:
        return True
    texto = payload.get("parent_texto") or payload.get("texto") or ""
    return bool(query_terms & set(tokenize(texto)))


def _filtro(tipo: str | None, incluir_expirados: bool, now: datetime) -> models.Filter | None:
    must = []
    if tipo:
        must.append(models.FieldCondition(key="tipo", match=models.MatchValue(value=tipo)))
    if not incluir_expirados:
        now_ts = int(now.timestamp())
        must.append(models.FieldCondition(key="vigencia_inicio_ts", range=models.Range(lte=now_ts)))
        must.append(models.FieldCondition(key="vigencia_fim_ts", range=models.Range(gte=now_ts)))
    if not must:
        return None
    return models.Filter(must=must)
