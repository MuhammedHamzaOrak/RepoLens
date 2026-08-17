import shutil
import sys
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class FakeEmbeddingProvider:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._document_embedding(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        lowered = text.lower()
        if any(
            keyword in lowered
            for keyword in (
                "greet",
                "register",
                "user",
                "kullanıcı",
                "kullanici",
                "kayıt",
                "kayit",
            )
        ):
            return [1.0, 0.0, 0.0]
        if any(keyword in lowered for keyword in ("readme", "documentation", "setup")):
            return [0.0, 1.0, 0.0]
        return [-1.0, -1.0, -1.0]

    def _document_embedding(self, text: str) -> list[float]:
        lowered = text.lower()
        if any(keyword in lowered for keyword in ("greet", "register", "user")):
            return [1.0, 0.0, 0.0]
        if any(keyword in lowered for keyword in ("readme", "documentation", "setup")):
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]


class FakeChatProvider:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append([dict(message) for message in messages])
        return "Kullanıcı kaydı register_user fonksiyonunda uygulanır."


@pytest.fixture()
def fake_chat_provider() -> FakeChatProvider:
    return FakeChatProvider()


@pytest.fixture(autouse=True)
def isolated_data_dir(
    monkeypatch: pytest.MonkeyPatch,
    fake_chat_provider: FakeChatProvider,
) -> None:
    from app.api import dependencies, projects
    from app.core.config import settings
    from app.repositories.database import init_db

    data_dir = BACKEND_DIR / ".test-data" / str(uuid.uuid4())
    monkeypatch.setattr(settings, "repolens_data_dir", str(data_dir))

    fake_provider = FakeEmbeddingProvider()
    monkeypatch.setattr(
        projects.indexing_service,
        "embedding_provider",
        fake_provider,
    )
    monkeypatch.setattr(
        projects.retrieval_service,
        "embedding_provider",
        fake_provider,
    )
    monkeypatch.setattr(
        dependencies.rag_service,
        "chat_provider",
        fake_chat_provider,
    )

    init_db()
    yield
    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture()
def workspace_tmp_path() -> Path:
    path = BACKEND_DIR / ".test-data" / str(uuid.uuid4())
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)
