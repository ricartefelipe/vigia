from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from vigia.errors import EspecialistaIndisponivel, IndiceIndisponivel
from vigia.models import Resposta
from vigia.orchestrator import Orchestrator
from vigia.service import RetrievalService


class BuscaRequest(BaseModel):
    consulta: str = Field(min_length=1)
    k: int = Field(default=4, ge=1, le=20)
    tipo: str | None = None
    incluir_expirados: bool = False


class PerguntaRequest(BaseModel):
    pergunta: str = Field(min_length=1)


def create_retrieval_app(service: RetrievalService) -> FastAPI:
    app = FastAPI(title="Vigia Retrieval")

    @app.get("/saude")
    def saude() -> dict:
        return {"status": "ok"}

    @app.post("/v1/buscar")
    def buscar(body: BuscaRequest) -> dict:
        try:
            citacoes = service.buscar(
                body.consulta,
                k=body.k,
                tipo=body.tipo,
                incluir_expirados=body.incluir_expirados,
            )
        except IndiceIndisponivel as exc:
            raise HTTPException(status_code=503, detail="indice indisponivel") from exc
        return {
            "citacoes": [_citacao(item) for item in citacoes],
            "motivo": None if citacoes else "sem_cobertura",
        }

    @app.get("/v1/trechos/{chunk_id}")
    def trecho(chunk_id: str) -> dict:
        try:
            citacao = service.trecho(chunk_id)
        except IndiceIndisponivel as exc:
            raise HTTPException(status_code=503, detail="indice indisponivel") from exc
        if citacao is None:
            raise HTTPException(status_code=404, detail="trecho ausente")
        return _citacao(citacao)

    @app.get("/v1/documentos/{doc_id}")
    def documento(doc_id: str) -> dict:
        try:
            found = service.documento(doc_id)
        except IndiceIndisponivel as exc:
            raise HTTPException(status_code=503, detail="indice indisponivel") from exc
        if found is None:
            raise HTTPException(status_code=404, detail="documento ausente")
        return found

    return app


def create_orchestrator_app(orchestrator: Orchestrator) -> FastAPI:
    app = FastAPI(title="Vigia Agentes")

    @app.get("/saude")
    def saude() -> dict:
        return {"status": "ok"}

    @app.post("/v1/perguntar")
    def perguntar(body: PerguntaRequest) -> dict:
        try:
            resposta = orchestrator.perguntar(body.pergunta)
        except IndiceIndisponivel as exc:
            raise HTTPException(status_code=503, detail="indice indisponivel") from exc
        except EspecialistaIndisponivel as exc:
            raise HTTPException(status_code=503, detail="especialista indisponivel") from exc
        return _resposta(resposta)

    return app


def _citacao(item) -> dict:
    return {
        "chunk_id": item.chunk_id,
        "doc_id": item.doc_id,
        "titulo": item.titulo,
        "tipo": item.tipo,
        "secao": item.secao,
        "texto": item.texto,
        "vigencia_fim": item.vigencia_fim,
    }


def _resposta(resposta: Resposta) -> dict:
    return {
        "resposta": resposta.resposta,
        "citacoes": [_citacao(item) for item in resposta.citacoes],
        "rota": resposta.rota,
        "revisao": resposta.revisao,
        "motivo": resposta.motivo,
    }
