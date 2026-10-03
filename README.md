# Vigia

Laboratório de arquitetura para normas internas de uma instituição financeira fictícia. O retrieval é um serviço. Os agentes não abrem o índice: normas entram por MCP, procedimentos por A2A. Resposta sem trecho vigente é recusada.

## Rodar

```bash
vigia chat
vigia web
```

`vigia web` abre em http://localhost:8080.

Digite a pergunta e pressione Enter. Linha vazia encerra. A resposta vem em texto, com a fonte embaixo.

No chat, uma pergunta curta como «e o prazo?» continua a anterior. Perguntas parafraseadas, como salário e empréstimo consignado, usam embedder multilíngue e, se o Ollama estiver no ar, a redação dele; sem o modelo baixado, a busca volta ao hash.

O mesmo serviço continua em JSON:

```bash
curl -s localhost:8000/v1/perguntar \
  -H 'content-type: application/json' \
  -d '{"pergunta":"Qual a margem máxima do crédito consignado?"}'
```

Para instalar e medir o retrieval:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
vigia avaliar
vigia perguntar "Qual a margem máxima do crédito consignado?"
vigia perguntar "Como contestar uma compra no cartão?"
```

Se o disco do projeto não aceitar o link da venv, crie o ambiente em outro diretório e instale a partir da raiz:

```bash
python3 -m venv /tmp/vigia-venv
/tmp/vigia-venv/bin/pip install -e ".[dev]"
```

`vigia avaliar` mede o recall@5 das três estratégias de chunking no conjunto em `eval/perguntas.jsonl`. A norma de cheque especial de 1999 está no índice e não pode voltar na busca padrão.

## Três processos

```bash
docker compose up --build
curl -s localhost:8000/v1/perguntar \
  -H 'content-type: application/json' \
  -d '{"pergunta":"Qual a margem máxima do crédito consignado?"}'
```

Depois de mudar o código dos agentes, reconstrua só esses dois serviços:

```bash
docker compose up -d --build agentes procedimentos
```

| Processo | Porta | Contrato |
| --- | --- | --- |
| retrieval | 8001 | `POST /v1/buscar`, `GET /v1/trechos/{id}`, `GET /v1/documentos/{id}` |
| procedimentos | 8002 | `GET /.well-known/agent-card.json`, `POST /a2a` com `message/send` |
| agentes | 8000 | `POST /v1/perguntar` |
| mcp | stdio | `initialize`, `tools/list`, `tools/call` |

O MCP sobe com `RETRIEVAL_URL` apontando para o retrieval:

```bash
RETRIEVAL_URL=http://127.0.0.1:8001 vigia mcp
```

## Decisões que o código sustenta

- Chunking atrás de uma interface: `fixed`, `heading` e `parent_child`. Em execução vale pai-filho: busca no trecho curto, citação na seção inteira.
- Índice híbrido no Qdrant. O vetor denso e o BM25 esparso são fundidos por RRF no nosso código. O BM25 é visível em `src/vigia/bm25.py`.
- Vigência é filtro de payload. Documento fora da data só volta com `incluir_expirados`.
- O revisor recusa frase cuja cobertura de tokens no trecho citado fica abaixo de 80%.
- Embedder e modelo são portas. O padrão `hash` é um vetor local determinístico para o laboratório rodar offline. `VIGIA_EMBEDDER=fastembed` ou `vertex` troca o vetor sem mudar o índice. `VIGIA_LLM=gemini` troca a redação; o revisor continua valendo.
- Kubernetes está em `infra/k8s/vigia.yaml`. Terraform de Artifact Registry, cluster Autopilot e Cloud Run está em `infra/terraform`.

## Mapa para a conversa

| Tema | Onde olhar |
| --- | --- |
| RAG, chunking, embeddings, banco vetorial | `src/vigia/chunking.py`, `embeddings.py`, `index.py` |
| Avaliação | `vigia avaliar`, `eval/perguntas.jsonl` |
| Multiagente e MCP | `src/vigia/mcp_server.py`, `orchestrator.py` |
| A2A | `src/vigia/a2a.py` |
| API e sistema distribuído | `src/vigia/api.py`, `docker-compose.yml` |
| GCP, Gemini, Vertex, GKE, Terraform | `embeddings.py`, `llm.py`, `infra/` |
| Ambiente regulado | filtro de vigência, citação obrigatória, log `vigia.auditoria` |
