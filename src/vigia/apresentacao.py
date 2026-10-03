from vigia.models import Resposta


def apresentar(resposta: Resposta) -> str:
    if resposta.revisao == "aceita" and resposta.resposta.strip():
        fontes = [
            f"Fonte: {citacao.titulo} — {citacao.secao} (até {citacao.vigencia_fim})"
            for citacao in resposta.citacoes
        ]
        if not fontes:
            return resposta.resposta
        return resposta.resposta + "\n\n" + "\n".join(fontes)
    if resposta.motivo == "sem_cobertura":
        return "Não há norma vigente sobre isso."
    return "Não dá para responder com o que está escrito nas normas."
