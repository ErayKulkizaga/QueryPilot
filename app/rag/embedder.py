from collections.abc import Callable

from app.llm.foundry_client import FoundryLocalClient


class FoundryEmbedder:
    def __init__(self, client: FoundryLocalClient) -> None:
        self._client = client

    def embed_documents(
        self,
        texts: list[str],
        *,
        download: bool = False,
        progress_callback: Callable[[float], None] | None = None,
    ) -> list[list[float]]:
        return self._client.embed(
            texts,
            download=download,
            progress_callback=progress_callback,
        )

    def embed_query(self, text: str) -> list[float]:
        return self._client.embed([text])[0]

