import json
import uuid
from dataclasses import asdict

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from vigia.errors import EspecialistaIndisponivel
from vigia.llm import LanguageModel
from vigia.models import Resposta
from vigia.review import revisar
from vigia.client import HttpRetrievalClient


class ProceduresAgent:
    def __init__(self, retrieval: HttpRetrievalClient, model: LanguageModel) -> None:
        self.retrieval = retrieval
        self.model = model

    def responder(self, pergunta: str) -> Resposta:
        citacoes = self.retrieval.buscar(pergunta, k=4, tipo="procedimento")
        if not citacoes:
            return Resposta("", [], "procedimento", "recusa", "sem_cobertura")
        texto = self.model.redigir(pergunta, citacoes)
        decisao = revisar(texto, citacoes)
        if decisao.decisao == "recusa":
            return Resposta("", citacoes, "procedimento", "recusa", decisao.motivo)
        return Resposta(texto, citacoes, "procedimento", "aceita", None)


class A2AClient:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def enviar(self, texto: str) -> Resposta:
        body = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": texto}],
                    "messageId": str(uuid.uuid4()),
                }
            },
        }
        try:
            response = self._client.post("/a2a", json=body)
        except httpx.HTTPError as exc:
            raise EspecialistaIndisponivel("especialista indisponivel") from exc
        if response.status_code >= 500:
            raise EspecialistaIndisponivel("especialista indisponivel")
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise EspecialistaIndisponivel(payload["error"].get("message", "a2a"))
        raw = payload["result"]["artifacts"][0]["parts"][0]["text"]
        return _resposta(json.loads(raw))


def create_a2a_app(agent: ProceduresAgent, public_url: str) -> FastAPI:
    app = FastAPI(title="Vigia Procedimentos")

    @app.get("/saude")
    def saude() -> dict:
        return {"status": "ok"}

    @app.get("/.well-known/agent-card.json")
    def card() -> dict:
        return agent_card(f"{public_url.rstrip('/')}/a2a")

    @app.post("/a2a")
    def rpc(body: dict):
        if body.get("method") != "message/send":
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {"code": -32601, "message": "method not found"},
                }
            )
        text = ""
        for part in (body.get("params") or {}).get("message", {}).get("parts", []):
            if part.get("kind") == "text":
                text = part.get("text") or ""
        resposta = agent.responder(text)
        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {
                "id": str(uuid.uuid4()),
                "contextId": str(uuid.uuid4()),
                "status": {"state": "completed"},
                "artifacts": [
                    {
                        "artifactId": str(uuid.uuid4()),
                        "name": "resposta",
                        "parts": [{"kind": "text", "text": json.dumps(_payload(resposta), ensure_ascii=False)}],
                    }
                ],
            },
        }

    return app


def agent_card(url: str) -> dict:
    return {
        "name": "Especialista de Procedimentos",
        "description": "Responde procedimentos operacionais com citação das rotinas vigentes.",
        "url": url,
        "version": "0.1.0",
        "protocolVersion": "0.3.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": "procedimentos",
                "name": "Procedimentos operacionais",
                "description": "Passo a passo de rotinas internas vigentes.",
                "tags": ["procedimentos", "operacao"],
            }
        ],
    }


def _payload(resposta: Resposta) -> dict:
    return {
        "resposta": resposta.resposta,
        "citacoes": [asdict(item) for item in resposta.citacoes],
        "revisao": resposta.revisao,
        "motivo": resposta.motivo,
    }


def _resposta(data: dict) -> Resposta:
    from vigia.models import Citacao

    return Resposta(
        resposta=data["resposta"],
        citacoes=[Citacao(**item) for item in data["citacoes"]],
        rota="procedimento",
        revisao=data["revisao"],
        motivo=data.get("motivo"),
    )
