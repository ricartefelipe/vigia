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
from vigia.orchestrator import Orchestrator
from vigia.service import RetrievalService
from vigia.wiring import avaliar_corpus, carregar_perguntas, open_index


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

    sub.add_parser("retrieval")
    sub.add_parser("procedimentos")
    sub.add_parser("agentes")
    sub.add_parser("mcp")

    args = parser.parse_args()
    if args.cmd == "ingest":
        _ingest(Path(args.corpus))
    elif args.cmd == "avaliar":
        _avaliar(Path(args.corpus), Path(args.golden))
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
