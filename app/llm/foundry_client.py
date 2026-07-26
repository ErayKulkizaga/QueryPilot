from collections.abc import Callable
from threading import Lock
from typing import Any


class FoundryLocalError(RuntimeError):
    """Raised when the optional Foundry Local runtime cannot serve a request."""


_manager: Any | None = None
_manager_lock = Lock()


def _get_manager(app_name: str) -> Any:
    global _manager
    if _manager is not None:
        return _manager

    with _manager_lock:
        if _manager is not None:
            return _manager
        try:
            from foundry_local_sdk import Configuration, FoundryLocalManager

            FoundryLocalManager.initialize(Configuration(app_name=app_name))
            _manager = FoundryLocalManager.instance
        except Exception as exc:
            raise FoundryLocalError(
                "Foundry Local could not be initialized. Install requirements-foundry.txt."
            ) from exc
    return _manager


class FoundryLocalClient:
    def __init__(
        self,
        *,
        app_name: str,
        chat_model_alias: str,
        embedding_model_alias: str,
    ) -> None:
        self._manager = _get_manager(app_name)
        self._chat_model_alias = chat_model_alias
        self._embedding_model_alias = embedding_model_alias
        self._loaded_models: dict[str, Any] = {}

    def model_status(self) -> dict[str, dict[str, Any]]:
        return {
            alias: self._status(alias)
            for alias in (self._chat_model_alias, self._embedding_model_alias)
        }

    def _status(self, alias: str) -> dict[str, Any]:
        model = self._manager.catalog.get_model(alias)
        if model is None:
            return {"available": False, "cached": False, "loaded": False}
        return {
            "available": True,
            "cached": bool(model.is_cached),
            "loaded": bool(model.is_loaded),
            "size_mb": model.info.file_size_mb,
            "task": model.info.task,
            "runtime": model.info.runtime.execution_provider,
        }

    def _prepare_model(
        self,
        alias: str,
        *,
        download: bool,
        progress_callback: Callable[[float], None] | None = None,
    ) -> Any:
        if alias in self._loaded_models:
            return self._loaded_models[alias]

        model = self._manager.catalog.get_model(alias)
        if model is None:
            raise FoundryLocalError(f"Foundry model alias is unavailable: {alias}")
        if not model.is_cached:
            if not download:
                raise FoundryLocalError(
                    f"Foundry model {alias} is not cached. Run the Foundry smoke script."
                )
            model.download(progress_callback)
        if not model.is_loaded:
            model.load()
        self._loaded_models[alias] = model
        return model

    def embed(
        self,
        texts: list[str],
        *,
        download: bool = False,
        progress_callback: Callable[[float], None] | None = None,
    ) -> list[list[float]]:
        if not texts:
            return []
        try:
            model = self._prepare_model(
                self._embedding_model_alias,
                download=download,
                progress_callback=progress_callback,
            )
            client = model.get_embedding_client()
            response = (
                client.generate_embedding(texts[0])
                if len(texts) == 1
                else client.generate_embeddings(texts)
            )
            return [list(item.embedding) for item in response.data]
        except FoundryLocalError:
            raise
        except Exception as exc:
            raise FoundryLocalError("Foundry Local embedding generation failed.") from exc

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        download: bool = False,
        progress_callback: Callable[[float], None] | None = None,
    ) -> str:
        try:
            model = self._prepare_model(
                self._chat_model_alias,
                download=download,
                progress_callback=progress_callback,
            )
            response = model.get_chat_client().complete_chat(messages)
            content = response.choices[0].message.content
            if not content:
                raise FoundryLocalError("Foundry Local returned an empty chat response.")
            return content
        except FoundryLocalError:
            raise
        except Exception as exc:
            raise FoundryLocalError("Foundry Local chat completion failed.") from exc

    def close(self) -> None:
        for model in self._loaded_models.values():
            if model.is_loaded:
                model.unload()
        self._loaded_models.clear()

    def __enter__(self) -> "FoundryLocalClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

