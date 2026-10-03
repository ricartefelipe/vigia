from pathlib import Path

from vigia.wiring import memory_service, responder

ROOT = Path(__file__).parents[1]


def test_parafrase_de_salario_acha_a_margem():
    service = memory_service()
    service.ingestir(ROOT / "corpus")
    resposta = responder(service, "quanto do salário pode ir para empréstimo consignado?")
    assert resposta.revisao == "aceita"
    assert "35%" in resposta.resposta
    assert any(item.doc_id == "norma-credito-003" for item in resposta.citacoes)


def test_pergunta_fora_do_corpus_fica_sem_cobertura():
    service = memory_service()
    service.ingestir(ROOT / "corpus")
    resposta = responder(service, "qual o horário da cafeteria do prédio?")
    assert resposta.motivo == "sem_cobertura"
    assert resposta.resposta == ""
