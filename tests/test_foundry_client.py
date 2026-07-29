from types import SimpleNamespace

import pytest

from app.llm.foundry_client import FoundryLocalClient, FoundryLocalError


class FakeModel:
    def __init__(self, *, cached: bool = True, loaded: bool = False) -> None:
        self.is_cached = cached
        self.is_loaded = loaded
        self.download_count = 0
        self.load_count = 0
        self.unload_count = 0
        self.info = SimpleNamespace(
            file_size_mb=512,
            task="chat",
            runtime=SimpleNamespace(execution_provider="CPU"),
        )
        self.embedding_data = [[0.1, 0.2]]
        self.chat_content = "accepted"

    def download(self, callback=None) -> None:
        self.download_count += 1
        self.is_cached = True
        if callback:
            callback(1.0)

    def load(self) -> None:
        self.load_count += 1
        self.is_loaded = True

    def unload(self) -> None:
        self.unload_count += 1
        self.is_loaded = False

    def get_embedding_client(self):
        model = self

        class EmbeddingClient:
            def generate_embedding(self, _text: str):
                return SimpleNamespace(
                    data=[
                        SimpleNamespace(embedding=item)
                        for item in model.embedding_data
                    ]
                )

            def generate_embeddings(self, _texts: list[str]):
                return self.generate_embedding("")

        return EmbeddingClient()

    def get_chat_client(self):
        model = self

        class ChatClient:
            def complete_chat(self, _messages):
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content=model.chat_content)
                        )
                    ]
                )

        return ChatClient()


class FakeCatalog:
    def __init__(self, models: dict[str, FakeModel]) -> None:
        self.models = models

    def get_model(self, alias: str):
        return self.models.get(alias)


def _client(monkeypatch, models: dict[str, FakeModel]) -> FoundryLocalClient:
    manager = SimpleNamespace(catalog=FakeCatalog(models))
    monkeypatch.setattr(
        "app.llm.foundry_client._get_manager",
        lambda _app_name: manager,
    )
    return FoundryLocalClient(
        app_name="querypilot-test",
        chat_model_alias="chat",
        embedding_model_alias="embedding",
    )


def test_foundry_client_reports_model_status(monkeypatch) -> None:
    chat = FakeModel(cached=True, loaded=True)
    client = _client(monkeypatch, {"chat": chat})

    status = client.model_status()

    assert status["chat"]["available"] is True
    assert status["chat"]["runtime"] == "CPU"
    assert status["embedding"] == {
        "available": False,
        "cached": False,
        "loaded": False,
    }


def test_foundry_client_requires_explicit_download(monkeypatch) -> None:
    client = _client(
        monkeypatch,
        {
            "chat": FakeModel(),
            "embedding": FakeModel(cached=False),
        },
    )

    with pytest.raises(FoundryLocalError, match="is not cached"):
        client.embed(["hello"])


def test_foundry_client_downloads_loads_embeds_and_reuses_model(
    monkeypatch,
) -> None:
    embedding = FakeModel(cached=False)
    embedding.embedding_data = [[0.1, 0.2], [0.3, 0.4]]
    client = _client(
        monkeypatch,
        {"chat": FakeModel(), "embedding": embedding},
    )
    progress: list[float] = []

    first = client.embed(
        ["one", "two"],
        download=True,
        progress_callback=progress.append,
    )
    second = client.embed(["one"])

    assert first == [[0.1, 0.2], [0.3, 0.4]]
    assert second == [[0.1, 0.2], [0.3, 0.4]]
    assert embedding.download_count == 1
    assert embedding.load_count == 1
    assert progress == [1.0]


def test_foundry_client_completes_and_closes_loaded_models(monkeypatch) -> None:
    chat = FakeModel(cached=True)
    client = _client(
        monkeypatch,
        {"chat": chat, "embedding": FakeModel()},
    )

    with client as opened:
        assert opened.complete([{"role": "user", "content": "hello"}]) == "accepted"

    assert chat.unload_count == 1


def test_foundry_client_rejects_empty_chat_response(monkeypatch) -> None:
    chat = FakeModel(cached=True)
    chat.chat_content = ""
    client = _client(
        monkeypatch,
        {"chat": chat, "embedding": FakeModel()},
    )

    with pytest.raises(FoundryLocalError, match="empty chat response"):
        client.complete([{"role": "user", "content": "hello"}])


def test_foundry_client_rejects_unknown_model_alias(monkeypatch) -> None:
    client = _client(monkeypatch, {})

    with pytest.raises(FoundryLocalError, match="alias is unavailable"):
        client.complete([{"role": "user", "content": "hello"}])
