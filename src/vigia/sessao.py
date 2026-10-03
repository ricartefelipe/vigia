import json
import re
from pathlib import Path

from vigia.models import Resposta
from vigia.text import tokenize

_SEGUIMENTO = re.compile(
    r"^(e|mas|ent[aã]o|qual|quais|quanto|quantos|quantas|em quanto|isso|esse|essa|desse|dessa|dele|dela|nesse|nessa)\b",
    re.IGNORECASE,
)


class Sessao:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.anterior = ""
        if path.exists():
            self.anterior = str(json.loads(path.read_text(encoding="utf-8")).get("anterior") or "")

    def efetivar(self, pergunta: str) -> str:
        if self.anterior and acompanhamento(pergunta):
            return f"{self.anterior.rstrip('? ')}? {pergunta}".strip()
        return pergunta

    def registrar(self, pergunta: str, resposta: Resposta) -> None:
        if resposta.revisao != "aceita":
            return
        self.anterior = pergunta
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"anterior": self.anterior}, ensure_ascii=False), encoding="utf-8")


def acompanhamento(pergunta: str) -> bool:
    texto = pergunta.strip()
    quantidade = len(tokenize(texto))
    if _SEGUIMENTO.search(texto) and quantidade <= 6:
        return True
    return quantidade <= 3
