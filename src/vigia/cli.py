import argparse
import json
import logging
import os
from dataclasses import asdict
from pathlib import Path

import httpx
import uvicorn

from vigia.a2a import A2AClient, ProceduresAgent, create_a2a_app
from vigia.api import create_orchestrator_app, create_retrieval_app
from vigia.client import HttpRetrievalClient
from vigia.llm import make_model
from vigia.mcp_server import NormasTools, serve_stdio
from vigia.models import Citacao, Resposta
from vigia.orchestrator import Orchestrator
from vigia.service import RetrievalService
from vigia.apresentacao import apresentar
from vigia.sessao import Sessao
from vigia.web import create_web_app
from vigia.wiring import avaliar_corpus, carregar_perguntas, memory_service, open_index, responder


def main() -> None:
    logging.basicConfig(level=os.environ.get("VIGIA_LOG", "WARNING"))
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(prog="vigia")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ingest = sub.add_parser("ingest")
    ingest.add_argument("--corpus", default="corpus")

    avaliar = sub.add_parser("avaliar")
    avaliar.add_argument("--corpus", default="corpus")
    avaliar.add_argument("--golden", default="eval/perguntas.jsonl")

    perguntar = sub.add_parser("perguntar")
    perguntar.add_argument("pergunta")
    perguntar.add_argument("--corpus", default="corpus")
    perguntar.add_argument("--json", action="store_true")

    chat = sub.add_parser("chat")
    chat.add_argument("--corpus", default="corpus")

    web = sub.add_parser("web")
    web.add_argument("--corpus", default="corpus")

    sub.add_parser("retrieval")
    sub.add_parser("procedimentos")
    sub.add_parser("agentes")
    sub.add_parser("mcp")

    args = parser.parse_args()
    if args.cmd == "ingest":
        _ingest(Path(args.corpus))
    elif args.cmd == "avaliar":
        _avaliar(Path(args.corpus), Path(args.golden))
    elif args.cmd == "perguntar":
        _perguntar(args.pergunta, Path(args.corpus), args.json)
    elif args.cmd == "chat":
        _chat(Path(args.corpus))
    elif args.cmd == "web":
        _web(Path(args.corpus))
    elif args.cmd == "retrieval":
        _retrieval()
    elif args.cmd == "procedimentos":
        _procedimentos()
    elif args.cmd == "agentes":
        _agentes()
    elif args.cmd == "mcp":
        _mcp()
    else:
        raise SystemExit(2)


def _ingest(corpus: Path) -> None:
    index = open_index(
        os.environ.get("QDRANT_URL"),
        os.environ.get("QDRANT_PATH", "data/qdrant"),
        Path(os.environ.get("VIGIA_VOCAB", "data/vocab.json")),
    )
    report = RetrievalService(index, os.environ.get("VIGIA_CHUNKING", "parent_child")).ingestir(corpus)
    print(json.dumps(asdict(report), ensure_ascii=False))


def _avaliar(corpus: Path, golden: Path) -> None:
    scores = avaliar_corpus(corpus, carregar_perguntas(golden))
    for strategy, score in scores.items():
        print(f"{strategy} {score:.2f}")


def _perguntar(pergunta: str, corpus: Path, como_json: bool) -> None:
    print(_saida(_com_memoria(pergunta, corpus), como_json))


def _chat(corpus: Path) -> None:
    print("Pergunte sobre as normas internas. Linha vazia encerra.")
    while True:
        try:
            pergunta = input("\n> ").strip()
        except EOFError:
            print()
            return
        if not pergunta:
            return
        print(_saida(_com_memoria(pergunta, corpus), False))


def _com_memoria(pergunta: str, corpus: Path) -> Resposta:
    sessao = Sessao(Path(os.environ.get("VIGIA_SESSAO", "data/sessao.json")))
    efetiva = sessao.efetivar(pergunta)
    resposta = _resolver(efetiva, corpus)
    sessao.registrar(efetiva, resposta)
    return resposta


def _web(corpus: Path) -> None:
    port = int(os.environ.get("PORT", "8080"))
    sessao = Path(os.environ.get("VIGIA_SESSAO", "data/sessao.json"))
    uvicorn.run(create_web_app(corpus, sessao), host="0.0.0.0", port=port)


def _resolver(pergunta: str, corpus: Path) -> Resposta:
    agentes = os.environ.get("AGENTES_URL")
    if agentes:
        remota = _perguntar_http(agentes, pergunta)
        if remota is not None:
            return remota
    if os.environ.get("RETRIEVAL_URL") and os.environ.get("A2A_URL"):
        retrieval = httpx.Client(base_url=os.environ["RETRIEVAL_URL"], timeout=30)
        a2a = httpx.Client(base_url=os.environ["A2A_URL"], timeout=30)
        try:
            return Orchestrator(
                NormasTools(HttpRetrievalClient(retrieval)),
                A2AClient(a2a),
                make_model(),
            ).perguntar(pergunta)
        finally:
            retrieval.close()
            a2a.close()
    service = memory_service(os.environ.get("VIGIA_CHUNKING", "parent_child"))
    service.ingestir(corpus)
    return responder(service, pergunta)


def _perguntar_http(url: str, pergunta: str) -> Resposta | None:
    try:
        response = httpx.post(
            f"{url.rstrip('/')}/v1/perguntar",
            json={"pergunta": pergunta},
            timeout=30,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    data = response.json()
    return Resposta(
        resposta=data["resposta"],
        citacoes=[Citacao(**item) for item in data["citacoes"]],
        rota=data["rota"],
        revisao=data["revisao"],
        motivo=data.get("motivo"),
    )


def _saida(resposta: Resposta, como_json: bool) -> str:
    if como_json:
        return json.dumps(_json(resposta), ensure_ascii=False, indent=2)
    return apresentar(resposta)


def _retrieval() -> None:
    index = open_index(
        os.environ.get("QDRANT_URL"),
        os.environ.get("QDRANT_PATH", "data/qdrant"),
        Path(os.environ.get("VIGIA_VOCAB", "data/vocab.json")),
    )
    service = RetrievalService(index, os.environ.get("VIGIA_CHUNKING", "parent_child"))
    if os.environ.get("VIGIA_INGEST_ON_START") == "1":
        report = service.ingestir(Path(os.environ.get("VIGIA_CORPUS", "corpus")))
        print(json.dumps(asdict(report), ensure_ascii=False))
    uvicorn.run(
        create_retrieval_app(service),
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8001")),
    )


def _procedimentos() -> None:
    retrieval = httpx.Client(base_url=os.environ["RETRIEVAL_URL"], timeout=30)
    app = create_a2a_app(
        ProceduresAgent(HttpRetrievalClient(retrieval), make_model()),
        os.environ.get("A2A_PUBLIC_URL", "http://localhost:8002"),
    )
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8002")))


def _agentes() -> None:
    retrieval = httpx.Client(base_url=os.environ["RETRIEVAL_URL"], timeout=30)
    a2a = httpx.Client(base_url=os.environ["A2A_URL"], timeout=30)
    app = create_orchestrator_app(
        Orchestrator(NormasTools(HttpRetrievalClient(retrieval)), A2AClient(a2a), make_model())
    )
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


def _mcp() -> None:
    retrieval = httpx.Client(base_url=os.environ["RETRIEVAL_URL"], timeout=30)
    serve_stdio(NormasTools(HttpRetrievalClient(retrieval)))


def _json(resposta: Resposta) -> dict:
    return {
        "resposta": resposta.resposta,
        "citacoes": [
            {
                "chunk_id": item.chunk_id,
                "doc_id": item.doc_id,
                "titulo": item.titulo,
                "tipo": item.tipo,
                "secao": item.secao,
                "texto": item.texto,
                "vigencia_fim": item.vigencia_fim,
            }
            for item in resposta.citacoes
        ],
        "rota": resposta.rota,
        "revisao": resposta.revisao,
        "motivo": resposta.motivo,
    }
