import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers.chat import ChatProviderError, FoundryLocalChatProvider


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _create_project(client: TestClient, *, index: bool) -> str:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr(
            "src/users.py",
            "def register_user(email):\n"
            "    return {'email': email}\n",
        )
        archive.writestr(
            "README.md",
            "# Setup\n\nInstall the project dependencies.\n",
        )
    response = client.post(
        "/api/projects",
        files={"file": ("chat.zip", archive_bytes.getvalue(), "application/zip")},
    )
    project_id = response.json()["project_id"]
    if index:
        assert client.post(f"/api/projects/{project_id}/index").status_code == 202
    return project_id


def test_chat_returns_grounded_answer_and_backend_owned_sources(
    client: TestClient,
    fake_chat_provider,
) -> None:
    project_id = _create_project(client, index=True)

    response = client.post(
        f"/api/projects/{project_id}/chat",
        json={"question": "Kullanıcı kaydı nerede yapılıyor?", "top_k": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer_status"] == "grounded"
    assert body["answer"] == "Kullanıcı kaydı register_user fonksiyonunda uygulanır."
    assert len(body["sources"]) == 1
    source = body["sources"][0]
    assert source["file_path"] == "src/users.py"
    assert source["symbol_name"] == "register_user"
    assert source["start_line"] == 1
    assert source["end_line"] == 2
    assert source["score"] == pytest.approx(1.0)
    assert source["snippet"].startswith("def register_user")
    source_view = client.get(
        f"/api/projects/{project_id}/chunks/{source['chunk_id']}"
    )
    assert source_view.status_code == 200
    assert source_view.json()["snippet"] == source["snippet"]
    assert source_view.json()["file_path"] == source["file_path"]

    assert len(fake_chat_provider.calls) == 1
    messages = fake_chat_provider.calls[0]
    assert "Never invent file paths" in messages[0]["content"]
    assert "Kullanıcı kaydı nerede yapılıyor?" in messages[1]["content"]
    assert "File: src/users.py" in messages[1]["content"]


def test_chat_skips_model_when_context_is_insufficient(
    client: TestClient,
    fake_chat_provider,
) -> None:
    project_id = _create_project(client, index=True)

    response = client.post(
        f"/api/projects/{project_id}/chat",
        json={"question": "Ödeme sistemi nasıl çalışıyor?"},
    )

    assert response.status_code == 200
    assert response.json()["answer_status"] == "insufficient_context"
    assert response.json()["sources"] == []
    assert fake_chat_provider.calls == []


def test_chat_handles_unknown_unindexed_and_blank_questions(
    client: TestClient,
    fake_chat_provider,
) -> None:
    assert client.post(
        "/api/projects/missing/chat",
        json={"question": "Bu proje ne yapıyor?"},
    ).status_code == 404

    project_id = _create_project(client, index=False)
    unindexed = client.post(
        f"/api/projects/{project_id}/chat",
        json={"question": "Bu proje ne yapıyor?"},
    )
    assert unindexed.status_code == 200
    assert unindexed.json()["answer_status"] == "indexing_incomplete"
    assert unindexed.json()["sources"] == []
    assert fake_chat_provider.calls == []

    blank = client.post(
        f"/api/projects/{project_id}/chat",
        json={"question": "   "},
    )
    assert blank.status_code == 422


def test_chat_provider_failure_returns_sanitized_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import dependencies

    class FailingChatProvider:
        def complete(self, messages) -> str:
            raise ChatProviderError("sensitive internal detail")

    project_id = _create_project(client, index=True)
    monkeypatch.setattr(
        dependencies.rag_service,
        "chat_provider",
        FailingChatProvider(),
    )

    response = client.post(
        f"/api/projects/{project_id}/chat",
        json={"question": "Kullanıcı kaydı nerede?"},
    )

    assert response.status_code == 503
    assert response.json()["answer_status"] == "error"
    assert response.json()["sources"] == []
    assert "sensitive internal detail" not in response.text


class StubChatClient:
    def __init__(self, completion) -> None:
        self.completion = completion
        self.messages = None

    def complete_chat(self, messages):
        self.messages = messages
        return self.completion


def test_foundry_chat_provider_returns_first_nonempty_choice() -> None:
    from types import SimpleNamespace

    completion = SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content="  grounded answer  "))
        ]
    )
    client = StubChatClient(completion)
    provider = FoundryLocalChatProvider("test-model", max_tokens=100, temperature=0)
    provider._client = client
    messages = [{"role": "user", "content": "question"}]

    assert provider.complete(messages) == "grounded answer"
    assert client.messages == messages


def test_foundry_chat_provider_rejects_empty_completion() -> None:
    from types import SimpleNamespace

    provider = FoundryLocalChatProvider("test-model", max_tokens=100, temperature=0)
    provider._client = StubChatClient(SimpleNamespace(choices=[]))

    with pytest.raises(ChatProviderError):
        provider.complete([{"role": "user", "content": "question"}])
