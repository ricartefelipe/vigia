import os
import re
from typing import Protocol

import httpx

from vigia.models import Citacao
from vigia.text import tokenize


class LanguageModel(Protocol):
    def redigir(self, pergunta: str, citacoes: list[Citacao]) -> str:
        pass


class ExtractiveModel:
    def redigir(self, pergunta: str, citacoes: list[Citacao]) -> str:
        frases = [frase for citacao in citacoes[:2] for frase in _frases(citacao.texto)]
        if not frases:
            return ""
        escolhida = _escolher(pergunta, frases)
        return _formular(pergunta, escolhida)


class GeminiModel:
    def __init__(self) -> None:
        self.model = os.environ.get("VIGIA_GEMINI_MODEL", "gemini-2.5-flash")

    def redigir(self, pergunta: str, citacoes: list[Citacao]) -> str:
        from google import genai

        if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in {"1", "true"}:
            client = genai.Client(
                vertexai=True,
                project=os.environ["GOOGLE_CLOUD_PROJECT"],
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
            )
        else:
            client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        contexto = "\n\n".join(
            f"[{citacao.doc_id} | {citacao.secao}]\n{citacao.texto}" for citacao in citacoes
        )
        prompt = (
            "Responda somente com o que estiver nos trechos. "
            "Se os trechos não cobrirem a pergunta, diga que não há base nas normas.\n\n"
            f"Trechos:\n{contexto}\n\nPergunta: {pergunta}"
        )
        response = client.models.generate_content(model=self.model, contents=prompt)
        return response.text or ""


def _frases(texto: str) -> list[str]:
    partes: list[str] = []
    atual: list[str] = []
    for char in texto:
        atual.append(char)
        if char in ".!?":
            frase = "".join(atual).strip()
            if frase:
                partes.append(frase)
            atual = []
    resto = "".join(atual).strip()
    if resto:
        partes.append(resto)
    return partes


class OllamaModel:
    def __init__(self) -> None:
        self.host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        self.model = os.environ.get("VIGIA_OLLAMA_MODEL") or _modelo_baixado(self.host)
        self._reserva = ExtractiveModel()

    def redigir(self, pergunta: str, citacoes: list[Citacao]) -> str:
        contexto = "\n\n".join(
            f"[{citacao.doc_id} | {citacao.secao}]\n{citacao.texto}" for citacao in citacoes
        )
        prompt = (
            "Responda em uma frase curta, em português, só com fatos dos trechos. "
            "Não invente número, prazo nem sigla. Não repita o trecho inteiro.\n\n"
            f"Trechos:\n{contexto}\n\nPergunta: {pergunta}"
        )
        try:
            response = httpx.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "think": False,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=45,
            )
            response.raise_for_status()
            texto = _limpar(str(response.json().get("message", {}).get("content") or ""))
        except httpx.HTTPError:
            return self._reserva.redigir(pergunta, citacoes)
        return texto or self._reserva.redigir(pergunta, citacoes)


def _escolher(pergunta: str, frases: list[str]) -> str:
    foco = _foco(pergunta)
    cosenos = _cosenos(pergunta, frases)
    ranqueadas = sorted(
        frases,
        key=lambda frase: (
            -len(foco & set(tokenize(frase))),
            -cosenos.get(frase, 0.0),
            len(frase),
        ),
    )
    return ranqueadas[0]


def _foco(pergunta: str) -> set[str]:
    pedacos = [pedaco.strip() for pedaco in re.split(r"\?", pergunta) if pedaco.strip()]
    alvo = pedacos[-1] if pedacos else pergunta
    return set(tokenize(alvo)) or set(tokenize(pergunta))


def _cosenos(pergunta: str, frases: list[str]) -> dict[str, float]:
    from vigia.embeddings import HashingEmbedder, make_embedder

    embedder = make_embedder()
    if isinstance(embedder, HashingEmbedder):
        return {}
    vetores = embedder.embed([pergunta, *frases])
    consulta = vetores[0]
    return {frase: _cosseno(consulta, vetor) for frase, vetor in zip(frases, vetores[1:], strict=True)}


def _cosseno(esquerda: list[float], direita: list[float]) -> float:
    produto = sum(a * b for a, b in zip(esquerda, direita, strict=True))
    norma_a = sum(a * a for a in esquerda) ** 0.5
    norma_b = sum(b * b for b in direita) ** 0.5
    if norma_a == 0 or norma_b == 0:
        return 0.0
    return produto / (norma_a * norma_b)


def _formular(pergunta: str, frase: str) -> str:
    partes = re.split(r"\s+é(?:\s+de)?\s+", frase, maxsplit=1, flags=re.IGNORECASE)
    if len(partes) != 2 or not partes[1].strip():
        return frase.strip()
    complemento = partes[1].strip().rstrip(".")
    if re.search(r"\d", complemento) and re.search(
        r"\b(quanto|quantos|quantas|salário|salario|margem|pode)\b",
        pergunta,
        re.IGNORECASE,
    ):
        return f"Até {complemento}."
    return f"É {complemento}."


def make_model() -> LanguageModel:
    kind = os.environ.get("VIGIA_LLM", "auto")
    if kind == "extrativo":
        return ExtractiveModel()
    if kind == "gemini":
        return GeminiModel()
    if kind == "ollama" or (kind == "auto" and _ollama_disponivel()):
        return OllamaModel()
    if kind == "auto" and (
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in {"1", "true"}
    ):
        return GeminiModel()
    return ExtractiveModel()


def _modelo_baixado(host: str) -> str:
    try:
        response = httpx.get(f"{host}/api/tags", timeout=0.4)
        response.raise_for_status()
        modelos = response.json().get("models") or []
        if modelos:
            return str(modelos[0]["name"])
    except httpx.HTTPError:
        pass
    return "llama3.2"


def _limpar(texto: str) -> str:
    sem_pensamento = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL)
    return sem_pensamento.strip()


def _ollama_disponivel() -> bool:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    try:
        response = httpx.get(f"{host}/api/tags", timeout=0.4)
    except httpx.HTTPError:
        return False
    return response.status_code == 200
