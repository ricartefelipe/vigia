from dataclasses import dataclass, field


@dataclass(frozen=True)
class Document:
    id: str
    titulo: str
    tipo: str
    vigencia_inicio: str
    vigencia_fim: str
    corpo: str
    origem: str


@dataclass(frozen=True)
class Chunk:
    id: str
    doc_id: str
    titulo: str
    tipo: str
    secao: str
    texto: str
    parent_texto: str
    vigencia_inicio: str
    vigencia_fim: str


@dataclass(frozen=True)
class Citacao:
    chunk_id: str
    doc_id: str
    titulo: str
    tipo: str
    secao: str
    texto: str
    vigencia_fim: str


@dataclass(frozen=True)
class Resposta:
    resposta: str
    citacoes: list[Citacao]
    rota: str
    revisao: str
    motivo: str | None


@dataclass
class IngestReport:
    documentos: int
    trechos: int
    falhas: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Revisao:
    decisao: str
    motivo: str | None
