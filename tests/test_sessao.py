from vigia.llm import ExtractiveModel
from vigia.models import Citacao, Resposta
from vigia.sessao import Sessao, acompanhamento


def test_seguimento_curto_continua_a_anterior(tmp_path):
    sessao = Sessao(tmp_path / "sessao.json")
    sessao.registrar(
        "Qual a margem máxima do crédito consignado?",
        Resposta("É 35% da renda líquida.", [], "norma", "aceita", None),
    )
    outra = Sessao(tmp_path / "sessao.json")
    assert acompanhamento("e o prazo?")
    assert outra.efetivar("e o prazo?").endswith("e o prazo?")
    assert "margem" in outra.efetivar("e o prazo?")


def test_formula_o_prazo_do_seguimento():
    citacao = Citacao(
        "c1",
        "norma-credito-003",
        "Política de Crédito Consignado",
        "norma",
        "Limites",
        "A margem máxima do crédito consignado é 35% da renda líquida. "
        "O prazo máximo do contrato é de 96 meses. "
        "Acima desses limites a proposta é recusada.",
        "2028-12-31",
    )
    texto = ExtractiveModel().redigir(
        "Qual a margem máxima do crédito consignado? e o prazo?",
        [citacao],
    )
    assert "96 meses" in texto
    assert "proposta é recusada" not in texto
