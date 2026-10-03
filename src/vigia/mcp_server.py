import json
from dataclasses import asdict
from typing import BinaryIO

from vigia.client import HttpRetrievalClient

_TOOLS = [
    {
        "name": "buscar",
        "description": "Busca trechos vigentes de normas internas para uma consulta.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "consulta": {"type": "string"},
                "k": {"type": "integer"},
                "tipo": {"type": "string"},
            },
            "required": ["consulta"],
        },
    },
    {
        "name": "ler_trecho",
        "description": "Lê um trecho pelo identificador.",
        "inputSchema": {
            "type": "object",
            "properties": {"chunk_id": {"type": "string"}},
            "required": ["chunk_id"],
        },
    },
    {
        "name": "ver_documento",
        "description": "Mostra vigência e tipo de um documento.",
        "inputSchema": {
            "type": "object",
            "properties": {"doc_id": {"type": "string"}},
            "required": ["doc_id"],
        },
    },
]


class NormasTools:
    def __init__(self, retrieval: HttpRetrievalClient) -> None:
        self.retrieval = retrieval

    def call(self, name: str, arguments: dict) -> str:
        if name == "buscar":
            citacoes = self.retrieval.buscar(
                arguments["consulta"],
                k=int(arguments.get("k", 4)),
                tipo=arguments.get("tipo") or "norma",
            )
            return json.dumps({"citacoes": [asdict(item) for item in citacoes]}, ensure_ascii=False)
        if name == "ler_trecho":
            citacao = self.retrieval.trecho(arguments["chunk_id"])
            if citacao is None:
                raise KeyError("trecho ausente")
            return json.dumps(asdict(citacao), ensure_ascii=False)
        if name == "ver_documento":
            documento = self.retrieval.documento(arguments["doc_id"])
            if documento is None:
                raise KeyError("documento ausente")
            return json.dumps(documento, ensure_ascii=False)
        raise KeyError(name)


def mcp_handle(request: dict, tools: NormasTools) -> dict | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return _result(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "vigia", "version": "0.1.0"},
            },
        )
    if method == "tools/list":
        return _result(request_id, {"tools": _TOOLS})
    if method == "tools/call":
        params = request.get("params") or {}
        try:
            text = tools.call(params.get("name"), params.get("arguments") or {})
        except KeyError as exc:
            return _result(
                request_id,
                {"content": [{"type": "text", "text": str(exc)}], "isError": True},
            )
        return _result(request_id, {"content": [{"type": "text", "text": text}], "isError": False})
    return _error(request_id, -32601, "method not found")


def frame(payload: dict) -> bytes:
    raw = json.dumps(payload).encode()
    return f"Content-Length: {len(raw)}\r\n\r\n".encode() + raw


def read_message(stream: BinaryIO) -> dict | None:
    headers = b""
    while b"\r\n\r\n" not in headers:
        chunk = stream.read(1)
        if not chunk:
            return None
        headers += chunk
        if len(headers) > 8192:
            raise ValueError("cabeçalho mcp grande demais")
    length = None
    for line in headers.decode().split("\r\n"):
        if line.lower().startswith("content-length:"):
            length = int(line.split(":", 1)[1].strip())
    if length is None:
        raise ValueError("content-length ausente")
    return json.loads(stream.read(length))


def serve_stdio(tools: NormasTools) -> None:
    import sys

    while True:
        message = read_message(sys.stdin.buffer)
        if message is None:
            return
        response = mcp_handle(message, tools)
        if response is None:
            continue
        sys.stdout.buffer.write(frame(response))
        sys.stdout.buffer.flush()


def _result(request_id: object, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: object, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
