import logging
import math
import threading
from collections.abc import Sequence
from typing import Protocol

from foundry_local_sdk import Configuration, FoundryLocalManager

logger = logging.getLogger(__name__)
_FOUNDRY_MANAGER_LOCK = threading.Lock()


class EmbeddingProviderError(RuntimeError):
    """Raised when the configured embedding provider cannot produce vectors."""


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


class FoundryLocalEmbeddingProvider:
    def __init__(self, model_alias: str) -> None:
        self.model_alias = model_alias
        self._client: object | None = None
        self._client_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        client = self._get_client()
        try:
            with self._inference_lock:
                response = client.generate_embeddings(list(texts))
            ordered_data = sorted(response.data, key=lambda item: item.index)
            embeddings = [list(item.embedding) for item in ordered_data]
            return self._validate_embeddings(embeddings, expected_count=len(texts))
        except EmbeddingProviderError:
            raise
        except Exception as exc:
            raise EmbeddingProviderError(
                "Foundry Local could not generate document embeddings."
            ) from exc

    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Query text must not be empty.")

        client = self._get_client()
        try:
            with self._inference_lock:
                response = client.generate_embedding(text)
            embeddings = [list(item.embedding) for item in response.data]
            return self._validate_embeddings(embeddings, expected_count=1)[0]
        except EmbeddingProviderError:
            raise
        except Exception as exc:
            raise EmbeddingProviderError(
                "Foundry Local could not generate the query embedding."
            ) from exc

    def _get_client(self) -> object:
        if self._client is not None:
            return self._client

        with self._client_lock:
            if self._client is not None:
                return self._client

            try:
                with _FOUNDRY_MANAGER_LOCK:
                    if FoundryLocalManager.instance is None:
                        FoundryLocalManager.initialize(Configuration(app_name="RepoLens"))

                manager = FoundryLocalManager.instance
                model = manager.catalog.get_model(self.model_alias)
                if model is None:
                    raise EmbeddingProviderError(
                        f"Foundry Local model '{self.model_alias}' is unavailable."
                    )

                if not model.is_cached:
                    logger.info(
                        "Downloading Foundry Local embedding model %s",
                        self.model_alias,
                    )
                    model.download(progress_callback=self._log_download_progress)
                if not model.is_loaded:
                    logger.info(
                        "Loading Foundry Local embedding model %s",
                        self.model_alias,
                    )
                    model.load()

                self._client = model.get_embedding_client()
                return self._client
            except EmbeddingProviderError:
                raise
            except Exception as exc:
                raise EmbeddingProviderError(
                    f"Foundry Local model '{self.model_alias}' could not be prepared."
                ) from exc

    def _log_download_progress(self, progress: float) -> None:
        logger.info(
            "Embedding model %s download progress: %.0f%%",
            self.model_alias,
            progress,
        )

    def _validate_embeddings(
        self,
        embeddings: list[list[float]],
        expected_count: int,
    ) -> list[list[float]]:
        if len(embeddings) != expected_count:
            raise EmbeddingProviderError(
                "Embedding provider returned an unexpected number of vectors."
            )
        if not embeddings or not embeddings[0]:
            raise EmbeddingProviderError("Embedding provider returned an empty vector.")

        dimensions = len(embeddings[0])
        normalized: list[list[float]] = []
        for embedding in embeddings:
            if len(embedding) != dimensions:
                raise EmbeddingProviderError(
                    "Embedding provider returned inconsistent vector dimensions."
                )
            vector = [float(value) for value in embedding]
            if not all(math.isfinite(value) for value in vector):
                raise EmbeddingProviderError(
                    "Embedding provider returned a non-finite vector value."
                )
            if not any(value != 0.0 for value in vector):
                raise EmbeddingProviderError(
                    "Embedding provider returned a zero vector."
                )
            normalized.append(vector)
        return normalized
