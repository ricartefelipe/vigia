import io
import json
from pathlib import Path

from fastapi.testclient import TestClient

from vigia.api import create_retrieval_app
from vigia.documents import load_document
from vigia.errors import DocumentoInvalido, IndiceIndisponivel
from vigia.mcp_server import NormasTools, frame, mcp_handle, read_message
from vigia.models import Citacao
from vigia.wiring import carregar_perguntas, memory_service, recall, responder

ROOT = Path(__file__).parents[1]
CORPUS = ROOT / "corpus"
GOLDEN = ROOT / "eval" / "perguntas.jsonl"


def test_documento_sem_frontmatter(tmp_path: Path):
    path = tmp_path / "ruim.md"
    path.write_text("sem cabecalho", encoding="utf-8")
    try:
        load_document(path)
    except DocumentoInvalido:
        return
    raise AssertionError("deveria falhar")


def test_recall_do_conjunto_dourado():
    service = memory_service()
    service.ingestir(CORPUS)
    assert recall(service, carregar_perguntas(GOLDEN)) == 1.0


def test_expirado_volta_quando_pedido():
    service = memory_service()
    service.ingestir(CORPUS)
    citacoes = service.buscar(
        "Qual a taxa do cheque especial promocional de 1999?",
        tipo="norma",
        incluir_expirados=True,
    )
    assert any(item.doc_id == "norma-cheque-1999" for item in citacoes)


def test_api_buscar_e_trecho():
    service = memory_service()
    service.ingestir(CORPUS)
    client = TestClient(create_retrieval_app(service))
    response = client.post("/v1/buscar", json={"consulta": "margem máxima do crédito consignado", "tipo": "norma"})
    assert response.status_code == 200
    body = response.json()
    assert body["citacoes"][0]["doc_id"] == "norma-credito-003"
    chunk_id = body["citacoes"][0]["chunk_id"]
    trecho = client.get(f"/v1/trechos/{chunk_id}")
    assert trecho.status_code == 200
    ausente = client.get("/v1/trechos/nao-existe")
    assert ausente.status_code == 404


def test_indice_indisponivel_vira_503():
    service = memory_service()

    class Quebrado:
        def query_points(self, **kwargs):
            raise ConnectionError("down")

        def scroll(self, **kwargs):
            raise ConnectionError("down")

    service.index.client = Quebrado()
    service.index.vocab = {"margem": 0}
    client = TestClient(create_retrieval_app(service))
    response = client.post("/v1/buscar", json={"consulta": "margem do consignado"})
    assert response.status_code == 503


def test_mcp_lista_e_chama_buscar():
    class Porta:
        def buscar(self, consulta, k=4, tipo=None, incluir_expirados=False):
            return [Citacao("c1", "norma-kyc-001", "KYC", "norma", "Identificação", "RG e CNH", "2028-12-31")]

        def trecho(self, chunk_id):
            return None

        def documento(self, doc_id):
            return None

    tools = NormasTools(Porta())
    listed = mcp_handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, tools)
    names = [item["name"] for item in listed["result"]["tools"]]
    assert names == ["buscar", "ler_trecho", "ver_documento"]
    called = mcp_handle(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "buscar", "arguments": {"consulta": "identidade"}},
        },
        tools,
    )
    payload = json.loads(called["result"]["content"][0]["text"])
    assert payload["citacoes"][0]["doc_id"] == "norma-kyc-001"


def test_frame_mcp():
    message = read_message(io.BytesIO(frame({"jsonrpc": "2.0", "id": 1, "method": "initialize"})))
    assert message["method"] == "initialize"


def test_pergunta_de_norma_passa_pelo_revisor():
    service = memory_service()
    service.ingestir(CORPUS)
    resposta = responder(service, "Qual a margem máxima do crédito consignado?")
    assert resposta.rota == "norma"
    assert resposta.revisao == "aceita"
    assert any(item.doc_id == "norma-credito-003" for item in resposta.citacoes)
    assert "35%" in resposta.resposta
    assert "proposta é recusada" not in resposta.resposta


def test_pergunta_de_procedimento_usa_a2a():
    service = memory_service()
    service.ingestir(CORPUS)
    resposta = responder(service, "Como contestar uma compra no cartão?")
    assert resposta.rota == "procedimento"
    assert resposta.revisao == "aceita"
    assert any(item.doc_id == "proc-contestacao-001" for item in resposta.citacoes)


def test_modelo_que_inventa_e_recusado():
    class Mentiroso:
        def redigir(self, pergunta, citacoes):
            return "A taxa administrativa é de nove por cento ao mês e não consta no texto."

    service = memory_service()
    service.ingestir(CORPUS)
    resposta = responder(service, "Qual a margem máxima do crédito consignado?", Mentiroso())
    assert resposta.revisao == "recusa"
    assert resposta.motivo == "sem_base"
    assert resposta.resposta == ""
    assert resposta.citacoes


def test_falha_de_arquivo_nao_interrompe_lote(tmp_path: Path):
    destino = tmp_path / "corpus"
    destino.mkdir()
    (destino / "ok.md").write_text(
        (CORPUS / "normas" / "credito.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (destino / "ruim.md").write_text("sem cabecalho", encoding="utf-8")
    report = memory_service().ingestir(destino)
    assert report.documentos == 1
    assert report.falhas


def test_excecao_de_indice_existe():
    assert issubclass(IndiceIndisponivel, RuntimeError)
