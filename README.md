# Vigia

Laboratório de arquitetura para normas internas de uma instituição financeira fictícia. Nesta base o retrieval já é um serviço: o índice devolve o trecho vigente e a avaliação mede o recall.

## Rodar

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -q
```

Se o disco do projeto não aceitar o link da venv, crie o ambiente em outro diretório e instale a partir da raiz:

```bash
python3 -m venv /tmp/vigia-venv
/tmp/vigia-venv/bin/pip install -e ".[dev]"
```

O conjunto em `eval/perguntas.jsonl` cobre o recall@5 das três estratégias de chunking. A norma de cheque especial de 1999 entra no índice e não pode voltar na busca padrão.

## Decisões

- Chunking atrás de uma interface: `fixed`, `heading` e `parent_child`. Em execução vale pai-filho: busca no trecho curto, citação na seção inteira.
- Índice híbrido no Qdrant. O vetor denso e o BM25 esparso são fundidos por RRF. O BM25 está em `src/vigia/bm25.py`.
- Vigência é filtro de payload. Documento fora da data só volta com `incluir_expirados`.
- O embedder padrão `hash` é um vetor local determinístico para o laboratório rodar offline.
