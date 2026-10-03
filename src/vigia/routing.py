import re

_PROCEDIMENTO = re.compile(
    r"\b(como (faço|fazer|solicitar|abrir|contestar)|passo a passo|procedimento)\b",
    re.IGNORECASE,
)


def rotear(pergunta: str) -> str:
    if _PROCEDIMENTO.search(pergunta):
        return "procedimento"
    return "norma"
