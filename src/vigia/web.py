from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from vigia.api import PerguntaRequest
from vigia.apresentacao import apresentar
from vigia.sessao import Sessao
from vigia.wiring import memory_service, responder

_PAGINA = """<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vigia</title>
  <style>
    body {
      margin: 0;
      font-family: system-ui, sans-serif;
      background: Canvas;
      color: CanvasText;
      line-height: 1.45;
    }
    main {
      max-width: 40rem;
      margin: 0 auto;
      padding: 2rem 1.25rem 7rem;
    }
    h1 {
      font-size: 1.25rem;
      font-weight: 600;
      margin: 0 0 1.5rem;
    }
    .turno { margin: 0 0 1.25rem; }
    .quem {
      display: block;
      font-size: 0.75rem;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      opacity: 0.6;
      margin-bottom: 0.25rem;
    }
    .corpo { white-space: pre-wrap; }
    form {
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      background: Canvas;
      border-top: 1px solid color-mix(in srgb, CanvasText 18%, transparent);
    }
    .barra {
      max-width: 40rem;
      margin: 0 auto;
      display: flex;
      gap: 0.5rem;
      padding: 0.75rem 1.25rem 1rem;
    }
    input, button {
      font: inherit;
      color: CanvasText;
      background: Canvas;
      border: 1px solid color-mix(in srgb, CanvasText 28%, transparent);
    }
    input { flex: 1; padding: 0.55rem 0.7rem; }
    button { padding: 0.55rem 0.9rem; cursor: pointer; }
  </style>
</head>
<body>
  <main>
    <h1>Vigia</h1>
    <div id="historico"></div>
  </main>
  <form id="form">
    <div class="barra">
      <input id="pergunta" name="pergunta" autocomplete="off" placeholder="Pergunta" required>
      <button type="submit">Enviar</button>
    </div>
  </form>
  <script>
    const historico = document.getElementById("historico");
    const form = document.getElementById("form");
    const campo = document.getElementById("pergunta");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const pergunta = campo.value.trim();
      if (!pergunta) return;
      campo.value = "";
      adicionar("Você", pergunta);
      const response = await fetch("/perguntar", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ pergunta }),
      });
      const data = await response.json();
      adicionar("Vigia", data.texto || "Não foi possível responder.");
    });
    function adicionar(quem, texto) {
      const bloco = document.createElement("div");
      bloco.className = "turno";
      const rotulo = document.createElement("span");
      rotulo.className = "quem";
      rotulo.textContent = quem;
      const corpo = document.createElement("div");
      corpo.className = "corpo";
      corpo.textContent = texto;
      bloco.append(rotulo, corpo);
      historico.append(bloco);
    }
  </script>
</body>
</html>
"""


def create_web_app(corpus: Path, sessao_path: Path) -> FastAPI:
    service = memory_service()
    service.ingestir(corpus)
    app = FastAPI(title="Vigia")

    @app.get("/", response_class=HTMLResponse)
    def pagina() -> str:
        return _PAGINA

    @app.post("/perguntar")
    def perguntar(body: PerguntaRequest) -> dict:
        sessao = Sessao(sessao_path)
        efetiva = sessao.efetivar(body.pergunta)
        resposta = responder(service, efetiva)
        sessao.registrar(efetiva, resposta)
        return {"texto": apresentar(resposta)}

    return app
