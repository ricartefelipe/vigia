import json
import logging

from vigia.a2a import A2AClient
from vigia.errors import EspecialistaIndisponivel
from vigia.llm import LanguageModel
from vigia.mcp_server import NormasTools, mcp_handle
from vigia.models import Citacao, Resposta
from vigia.review import revisar
from vigia.routing import rotear

_log = logging.getLogger("vigia.auditoria")


class Orchestrator:
    def __init__(self, tools: NormasTools, a2a: A2AClient, model: LanguageModel) -> None:
        self.tools = tools
        self.a2a = a2a
        self.model = model

    def perguntar(self, pergunta: str) -> Resposta:
        rota = rotear(pergunta)
        if rota == "procedimento":
            resposta = self._via_a2a(pergunta)
        else:
            resposta = self._via_mcp(pergunta)
        _log.info(
            json.dumps(
                {
                    "pergunta": pergunta,
                    "rota": resposta.rota,
                    "revisao": resposta.revisao,
                    "motivo": resposta.motivo,
                    "documentos": [item.doc_id for item in resposta.citacoes],
                },
                ensure_ascii=False,
            )
        )
        return resposta

    def _via_mcp(self, pergunta: str) -> Resposta:
        raw = mcp_handle(
            {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {
                    "name": "buscar",
                    "arguments": {"consulta": pergunta, "k": 4, "tipo": "norma"},
                },
            },
            self.tools,
        )
        content = raw["result"]["content"][0]
        if raw["result"].get("isError"):
            raise EspecialistaIndisponivel(content["text"])
        citacoes = [Citacao(**item) for item in json.loads(content["text"])["citacoes"]]
        return _fechar("norma", pergunta, citacoes, self.model)

    def _via_a2a(self, pergunta: str) -> Resposta:
        recebida = self.a2a.enviar(pergunta)
        if recebida.revisao == "recusa":
            return recebida
        decisao = revisar(recebida.resposta, recebida.citacoes)
        if decisao.decisao == "recusa":
            return Resposta("", recebida.citacoes, "procedimento", "recusa", decisao.motivo)
        return recebida


def _fechar(rota: str, pergunta: str, citacoes: list[Citacao], model: LanguageModel) -> Resposta:
    if not citacoes:
        return Resposta("", [], rota, "recusa", "sem_cobertura")
    texto = model.redigir(pergunta, citacoes)
    decisao = revisar(texto, citacoes)
    if decisao.decisao == "recusa":
        return Resposta("", citacoes, rota, "recusa", decisao.motivo)
    return Resposta(texto, citacoes, rota, "aceita", None)
