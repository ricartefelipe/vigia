from datetime import date
from pathlib import Path

import yaml

from vigia.errors import DocumentoInvalido
from vigia.models import Document

_TIPOS = {"norma", "procedimento"}


def load_document(path: Path) -> Document:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise DocumentoInvalido("frontmatter ausente")
    parts = raw.split("---", 2)
    if len(parts) < 3:
        raise DocumentoInvalido("frontmatter ausente")
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise DocumentoInvalido("frontmatter ilegível") from exc
    if not isinstance(meta, dict):
        raise DocumentoInvalido("frontmatter ilegível")
    doc_id = str(meta.get("id") or "").strip()
    titulo = str(meta.get("titulo") or "").strip()
    tipo = str(meta.get("tipo") or "").strip()
    if not doc_id or not titulo:
        raise DocumentoInvalido("id e titulo são obrigatórios")
    if tipo not in _TIPOS:
        raise DocumentoInvalido("tipo deve ser norma ou procedimento")
    corpo = parts[2].strip()
    if not corpo:
        raise DocumentoInvalido("corpo vazio")
    return Document(
        id=doc_id,
        titulo=titulo,
        tipo=tipo,
        vigencia_inicio=_data(meta.get("vigencia_inicio"), "vigencia_inicio"),
        vigencia_fim=_data(meta.get("vigencia_fim"), "vigencia_fim"),
        corpo=corpo,
        origem=str(path),
    )


def _data(value: object, campo: str) -> str:
    if hasattr(value, "isoformat"):
        texto = value.isoformat()
    else:
        texto = str(value or "").strip()
    try:
        date.fromisoformat(texto)
    except ValueError as exc:
        raise DocumentoInvalido(f"{campo} inválida") from exc
    return texto
