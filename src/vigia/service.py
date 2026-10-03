from datetime import datetime, timezone
from pathlib import Path

from vigia.chunking import chunk_document
from vigia.documents import load_document
from vigia.errors import DocumentoInvalido
from vigia.index import Index
from vigia.models import Citacao, IngestReport


class RetrievalService:
    def __init__(self, index: Index, strategy: str = "parent_child") -> None:
        self.index = index
        self.strategy = strategy

    def ingestir(self, diretorio: Path) -> IngestReport:
        documents = []
        falhas: list[str] = []
        for path in sorted(diretorio.rglob("*.md")):
            try:
                documents.append(load_document(path))
            except DocumentoInvalido as exc:
                falhas.append(f"{path.name}: {exc}")
        chunks = []
        for document in documents:
            chunks.extend(chunk_document(document, self.strategy))
        self.index.rebuild(chunks)
        return IngestReport(documentos=len(documents), trechos=len(chunks), falhas=falhas)

    def buscar(
        self,
        consulta: str,
        k: int = 4,
        tipo: str | None = None,
        incluir_expirados: bool = False,
        now: datetime | None = None,
    ) -> list[Citacao]:
        return self.index.search(consulta, k, tipo, incluir_expirados, now or datetime.now(timezone.utc))

    def trecho(self, chunk_id: str) -> Citacao | None:
        return self.index.trecho(chunk_id)

    def documento(self, doc_id: str) -> dict | None:
        return self.index.documento(doc_id)
