from vigia.chunking import chunk_document, windows
from vigia.models import Document


def _doc(corpo: str) -> Document:
    return Document(
        id="doc",
        titulo="Titulo",
        tipo="norma",
        vigencia_inicio="2024-01-01",
        vigencia_fim="2028-12-31",
        corpo=corpo,
        origem="memoria",
    )


def test_janela_quebra_texto_longo():
    partes = windows(("regra " * 200).strip())
    assert len(partes) > 1
    assert all(partes)


def test_pai_filho_guarda_a_secao_inteira():
    corpo = "# Limites\n\n" + ("margem consignado. " * 80)
    chunks = chunk_document(_doc(corpo), "parent_child")
    assert len(chunks) > 1
    assert len(chunks[0].texto) < len(chunks[0].parent_texto)
    assert "margem consignado" in chunks[0].parent_texto


def test_heading_respeita_secoes():
    corpo = "# Uma\n\nalfa\n\n# Duas\n\nbeta"
    chunks = chunk_document(_doc(corpo), "heading")
    assert [chunk.secao for chunk in chunks] == ["Uma", "Duas"]


def test_estrategia_desconhecida():
    try:
        chunk_document(_doc("texto"), "outra")
    except ValueError as exc:
        assert "desconhecida" in str(exc)
    else:
        raise AssertionError("deveria falhar")

