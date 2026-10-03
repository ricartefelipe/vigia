import re

from vigia.models import Citacao, Revisao

_PALAVRA_NUMERO = {
    "zero": "0",
    "dois": "2",
    "duas": "2",
    "tres": "3",
    "três": "3",
    "quatro": "4",
    "cinco": "5",
    "seis": "6",
    "sete": "7",
    "oito": "8",
    "nove": "9",
    "dez": "10",
    "onze": "11",
    "doze": "12",
    "vinte": "20",
    "trinta": "30",
    "quarenta": "40",
    "cinquenta": "50",
    "sessenta": "60",
    "setenta": "70",
    "oitenta": "80",
    "noventa": "90",
    "cem": "100",
    "mil": "1000",
}
_NUMERO = re.compile(r"\d+(?:[.,]\d+)?")
_PALAVRA = re.compile(
    r"\b(zero|dois|duas|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|vinte|trinta|quarenta|cinquenta|sessenta|setenta|oitenta|noventa|cem|mil)\b"
    r"(?:\s+(?:%|por\s+cento|dias?|meses|m[eê]s|horas?|anos?))",
    re.IGNORECASE,
)
_SIGLA = re.compile(r"\b[A-Z]{2,}\b")


def revisar(resposta: str, citacoes: list[Citacao]) -> Revisao:
    if not citacoes:
        return Revisao("recusa", "sem_cobertura")
    if not resposta.strip():
        return Revisao("recusa", "sem_base")
    base = " ".join(f"{item.titulo} {item.secao} {item.texto}" for item in citacoes)
    if not extrair_fatos(resposta) <= extrair_fatos(base):
        return Revisao("recusa", "sem_base")
    return Revisao("aceita", None)


def extrair_fatos(texto: str) -> set[str]:
    fatos = {f"n:{_canon(item.group())}" for item in _NUMERO.finditer(texto)}
    for item in _PALAVRA.finditer(texto):
        chave = item.group(1).lower()
        if chave in _PALAVRA_NUMERO:
            fatos.add(f"n:{_PALAVRA_NUMERO[chave]}")
    fatos.update(f"s:{item.group().casefold()}" for item in _SIGLA.finditer(texto))
    return fatos


def _canon(numero: str) -> str:
    texto = numero.replace(",", ".").rstrip("%")
    if texto.endswith(".0"):
        return texto[:-2]
    return texto
