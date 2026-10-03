import re

_TOKEN = re.compile(r"[0-9A-Za-zÀ-ÿ]+")
_STOP = frozenset(
    """
    a o os as de da do das dos e em para com um uma que no na nos nas por
    ao aos à às ou se sua seu suas seus não sim já mais menos quando onde
    """.split()
)


def tokenize(texto: str) -> list[str]:
    tokens = []
    for bruto in _TOKEN.findall(texto.lower()):
        if len(bruto) < 2 or bruto in _STOP:
            continue
        tokens.append(bruto)
    return tokens
