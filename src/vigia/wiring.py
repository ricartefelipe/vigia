import json
import time
import warnings
from pathlib import Path

from qdrant_client import QdrantClient

from vigia.a2a import A2AClient, ProceduresAgent, create_a2a_app
from vigia.api import create_retrieval_app
from vigia.chunking import STRATEGIES
from vigia.client import HttpRetrievalClient
from vigia.embeddings import HashingEmbedder, make_embedder
from vigia.errors import IndiceIndisponivel
from vigia.index import Index
from vigia.llm import LanguageModel, make_model
from vigia.mcp_server import NormasTools
from vigia.models import Resposta
from vigia.orchestrator import Orchestrator
from vigia.service import RetrievalService


def memory_service(strategy: str = "parent_child", embedder=None) -> RetrievalService:
    index = Index(QdrantClient(":memory:"), embedder or make_embedder())
    return RetrievalService(index, strategy)


def responder(
    service: RetrievalService,
    pergunta: str,
    model: LanguageModel | None = None,
) -> Resposta:
    chosen = model or make_model()
    warnings.filterwarnings(
        "ignore",
        message="Using `httpx` with `starlette.testclient`",
    )
    from fastapi.testclient import TestClient

    retrieval_http = TestClient(create_retrieval_app(service))
    a2a_http = TestClient(
        create_a2a_app(
            ProceduresAgent(HttpRetrievalClient(retrieval_http), chosen),
            "http://procedimentos",
        )
    )
    try:
        orchestrator = Orchestrator(
            NormasTools(HttpRetrievalClient(retrieval_http)),
            A2AClient(a2a_http),
            chosen,
        )
        return orchestrator.perguntar(pergunta)
    finally:
        a2a_http.close()
        retrieval_http.close()


def carregar_perguntas(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def recall(service: RetrievalService, perguntas: list[dict], k: int = 5) -> float:
    if not perguntas:
        return 0.0
    acertos = 0
    for item in perguntas:
        citacoes = service.buscar(item["consulta"], k=k, tipo=item.get("tipo"))
        obtidos = {citacao.doc_id for citacao in citacoes}
        esperados = set(item["esperados"])
        if esperados:
            acertos += int(bool(obtidos & esperados))
        else:
            acertos += int(not obtidos)
    return acertos / len(perguntas)


def avaliar_corpus(corpus: Path, perguntas: list[dict], embedder=None) -> dict[str, float]:
    scores = {}
    for strategy in STRATEGIES:
        service = memory_service(strategy, embedder or HashingEmbedder())
        service.ingestir(corpus)
        scores[strategy] = recall(service, perguntas)
    return scores


def open_index(url: str | None, path: str, vocab: Path, embedder=None) -> Index:
    if url:
        client = _client_remoto(url)
    else:
        Path(path).mkdir(parents=True, exist_ok=True)
        client = QdrantClient(path=path)
    return Index(client, embedder or make_embedder(), vocab_path=vocab)


def _client_remoto(url: str) -> QdrantClient:
    last: Exception | None = None
    for _ in range(20):
        try:
            client = QdrantClient(url=url)
            client.get_collections()
            return client
        except Exception as exc:
            last = exc
            time.sleep(0.5)
    raise IndiceIndisponivel("indice indisponivel") from last
