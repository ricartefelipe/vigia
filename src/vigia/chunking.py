from vigia.models import Chunk, Document

STRATEGIES = ("fixed", "heading", "parent_child")
_SIZE = 480
_OVERLAP = 80


def chunk_document(document: Document, strategy: str) -> list[Chunk]:
    if strategy == "fixed":
        return _fixed(document)
    if strategy == "heading":
        return _heading(document)
    if strategy == "parent_child":
        return _parent_child(document)
    raise ValueError(f"estratégia desconhecida: {strategy}")


def windows(texto: str, size: int = _SIZE, overlap: int = _OVERLAP) -> list[str]:
    texto = texto.strip()
    if not texto:
        return []
    if len(texto) <= size:
        return [texto]
    parts: list[str] = []
    start = 0
    while start < len(texto):
        end = min(len(texto), start + size)
        if end < len(texto):
            space = texto.rfind(" ", start, end)
            if space > start + size // 2:
                end = space
        piece = texto[start:end].strip()
        if piece:
            parts.append(piece)
        if end >= len(texto):
            break
        start = max(end - overlap, start + 1)
    return parts


def sections(corpo: str) -> list[tuple[str, str]]:
    titulo = "Introdução"
    buffer: list[str] = []
    found: list[tuple[str, str]] = []

    def flush() -> None:
        texto = "\n".join(buffer).strip()
        if texto:
            found.append((titulo, texto))

    for line in corpo.splitlines():
        if line.startswith("#"):
            flush()
            buffer = []
            titulo = line.lstrip("#").strip() or "Seção"
        else:
            buffer.append(line)
    flush()
    return found


def _chunk(
    document: Document,
    secao: str,
    texto: str,
    parent_texto: str,
    numero: int,
    strategy: str,
) -> Chunk:
    return Chunk(
        id=f"{document.id}:{strategy}:{numero}",
        doc_id=document.id,
        titulo=document.titulo,
        tipo=document.tipo,
        secao=secao,
        texto=texto,
        parent_texto=parent_texto,
        vigencia_inicio=document.vigencia_inicio,
        vigencia_fim=document.vigencia_fim,
    )


def _fixed(document: Document) -> list[Chunk]:
    return [
        _chunk(document, "Documento", piece, piece, numero, "fixed")
        for numero, piece in enumerate(windows(document.corpo))
    ]


def _heading(document: Document) -> list[Chunk]:
    return [
        _chunk(document, titulo, texto, texto, numero, "heading")
        for numero, (titulo, texto) in enumerate(sections(document.corpo))
    ]


def _parent_child(document: Document) -> list[Chunk]:
    chunks: list[Chunk] = []
    numero = 0
    for titulo, texto in sections(document.corpo):
        for piece in windows(texto):
            chunks.append(_chunk(document, titulo, piece, texto, numero, "parent_child"))
            numero += 1
    return chunks
