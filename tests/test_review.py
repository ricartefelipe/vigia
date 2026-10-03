from vigia.models import Citacao
from vigia.review import revisar
from vigia.routing import rotear


def _citacao(texto: str) -> Citacao:
    return Citacao("c1", "doc", "Titulo", "norma", "Secao", texto, "2028-12-31")


def test_aceita_texto_ancorado():
    base = "A margem máxima do crédito consignado é 35% da renda líquida."
    decisao = revisar(base, [_citacao(base)])
    assert decisao.decisao == "aceita"


def test_recusa_frase_sem_base():
    base = "A margem máxima do crédito consignado é 35% da renda líquida."
    decisao = revisar(
        "A taxa administrativa é de nove por cento ao mês e não consta no texto.",
        [_citacao(base)],
    )
    assert decisao.decisao == "recusa"
    assert decisao.motivo == "sem_base"


def test_aceita_formulacao_com_o_mesmo_numero():
    base = "A margem máxima do crédito consignado é 35% da renda líquida."
    decisao = revisar("A margem fica em 35% da renda líquida.", [_citacao(base)])
    assert decisao.decisao == "aceita"


def test_recusa_sem_citacao():
    decisao = revisar("qualquer coisa", [])
    assert decisao.motivo == "sem_cobertura"


def test_roteia_procedimento_e_norma():
    assert rotear("Como contestar uma compra no cartão?") == "procedimento"
    assert rotear("Qual a margem máxima do crédito consignado?") == "norma"
