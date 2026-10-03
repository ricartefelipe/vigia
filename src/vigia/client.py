import httpx

from vigia.errors import IndiceIndisponivel
from vigia.models import Citacao


class HttpRetrievalClient:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def buscar(
        self,
        consulta: str,
        k: int = 4,
        tipo: str | None = None,
        incluir_expirados: bool = False,
    ) -> list[Citacao]:
        response = self._client.post(
            "/v1/buscar",
            json={
                "consulta": consulta,
                "k": k,
                "tipo": tipo,
                "incluir_expirados": incluir_expirados,
            },
        )
        if response.status_code == 503:
            raise IndiceIndisponivel(response.text)
        response.raise_for_status()
        return [Citacao(**item) for item in response.json()["citacoes"]]

    def trecho(self, chunk_id: str) -> Citacao | None:
        response = self._client.get(f"/v1/trechos/{chunk_id}")
        if response.status_code == 404:
            return None
        if response.status_code == 503:
            raise IndiceIndisponivel(response.text)
        response.raise_for_status()
        return Citacao(**response.json())

    def documento(self, doc_id: str) -> dict | None:
        response = self._client.get(f"/v1/documentos/{doc_id}")
        if response.status_code == 404:
            return None
        if response.status_code == 503:
            raise IndiceIndisponivel(response.text)
        response.raise_for_status()
        return response.json()
