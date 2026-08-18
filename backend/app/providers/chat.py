import threading
from collections.abc import Sequence
from typing import Literal, Protocol, TypedDict

from app.providers.foundry_local import FoundryLocalRuntimeError, get_ready_model


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatProviderError(RuntimeError):
    """Raised when the configured chat provider cannot produce an answer."""


class ChatProvider(Protocol):
    def complete(self, messages: Sequence[ChatMessage]) -> str:
        ...


class FoundryLocalChatProvider:
    def __init__(
        self,
        model_alias: str,
        max_tokens: int,
        temperature: float,
        frequency_penalty: float | None = None,
        random_seed: int | None = None,
    ) -> None:
        self.model_alias = model_alias
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.frequency_penalty = frequency_penalty
        self.random_seed = random_seed
        self._client: object | None = None
        self._client_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def complete(self, messages: Sequence[ChatMessage]) -> str:
        if not messages:
            raise ValueError("Chat messages must not be empty.")
        if any(not message["content"].strip() for message in messages):
            raise ValueError("Chat message content must not be empty.")

        client = self._get_client()
        try:
            with self._inference_lock:
                completion = client.complete_chat(list(messages))
            if not completion.choices:
                raise ChatProviderError("Chat provider returned no choices.")
            raw_answer = completion.choices[0].message.content
            if not isinstance(raw_answer, str) or not raw_answer.strip():
                raise ChatProviderError("Chat provider returned an empty answer.")
            return raw_answer.strip()
        except ChatProviderError:
            raise
        except Exception as exc:
            raise ChatProviderError(
                "Foundry Local could not generate a chat completion."
            ) from exc

    def _get_client(self) -> object:
        if self._client is not None:
            return self._client

        with self._client_lock:
            if self._client is not None:
                return self._client
            try:
                model = get_ready_model(self.model_alias)
                client = model.get_chat_client()
                client.settings.max_tokens = self.max_tokens
                client.settings.temperature = self.temperature
                client.settings.frequency_penalty = self.frequency_penalty
                client.settings.random_seed = self.random_seed
                self._client = client
                return self._client
            except FoundryLocalRuntimeError as exc:
                raise ChatProviderError(str(exc)) from exc
            except Exception as exc:
                raise ChatProviderError(
                    f"Foundry Local model '{self.model_alias}' could not be prepared."
                ) from exc
