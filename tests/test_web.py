from pathlib import Path

from fastapi.testclient import TestClient

from vigia.web import create_web_app

ROOT = Path(__file__).parents[1]


def test_pagina_e_pergunta(tmp_path: Path):
    app = create_web_app(ROOT / "corpus", tmp_path / "sessao.json")
    client = TestClient(app)
    pagina = client.get("/")
    assert pagina.status_code == 200
    assert "<form" in pagina.text
    assert "Enviar" in pagina.text
    resposta = client.post(
        "/perguntar",
        json={"pergunta": "Qual a margem máxima do crédito consignado?"},
    )
    assert resposta.status_code == 200
    texto = resposta.json()["texto"]
    assert "35%" in texto
    assert "Fonte:" in texto
    assert texto.strip().startswith("{") is False
