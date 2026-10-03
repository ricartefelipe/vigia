# Arquitetura

Uma pergunta segue um destes caminhos.

Norma. O orquestrador chama a ferramenta MCP `buscar`. O servidor MCP faz HTTP no retrieval. O retrieval devolve trechos vigentes, com documento, seção e vigência. O modelo redige só a partir desses trechos. O revisor confere a ancoragem. Se a frase não estiver coberta, a resposta vai vazia e o motivo fica `sem_base`. Se não houver trecho, o motivo fica `sem_cobertura`.

Procedimento. O orquestrador não chama o retrieval. Ele envia `message/send` para o especialista, que publica agent card em `/.well-known/agent-card.json`. Esse especialista consulta o retrieval com `tipo=procedimento`, revisa a própria resposta e devolve o JSON num artifact. O orquestrador revisa de novo.

O índice não é biblioteca compartilhada entre os processos. Quem não é o retrieval passa por HTTP.

## Ingestão

Markdown com frontmatter (`id`, `titulo`, `tipo`, `vigencia_inicio`, `vigencia_fim`). Arquivo inválido sai do lote e entra no relatório. Os outros seguem. A coleção é recriada a cada ingestão.

## Busca

1. Embedding da consulta e vetor esparso das palavras que existem no vocabulário.
2. Duas buscas no Qdrant, com o mesmo filtro de tipo e vigência.
3. Fusão por RRF.
4. Um hit só permanece se compartilha termo com a consulta ou se o cosseno denso passa de 0,72.
5. Deduplicação por documento e seção.

A citação devolve o texto pai quando a estratégia é pai-filho.

## O que fica de fora

Não há tela, login, fila nem multi-tenant. O laboratório existe para percorrer RAG avaliável, contrato de agentes, MCP, A2A e a troca de provedor até o empacotamento em GCP.
