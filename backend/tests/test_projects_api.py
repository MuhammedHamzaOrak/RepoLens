import io
import shutil
import stat
import sys
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.main import app
from app.repositories.chunk_repository import ChunkRepository


@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.repositories.database import init_db

    data_dir = BACKEND_DIR / ".test-data" / str(uuid.uuid4())
    monkeypatch.setattr(settings, "repolens_data_dir", str(data_dir))
    init_db()
    yield
    shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_create_project_accepts_zip_and_saves_upload(client: TestClient) -> None:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("README.md", "hello")

    response = client.post(
        "/api/projects",
        files={"file": ("repo.zip", archive_bytes.getvalue(), "application/zip")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "repo.zip"
    assert body["project_id"]

    upload_dir = Path(settings.repolens_data_dir) / "uploads" / body["project_id"]
    assert (upload_dir / "source.zip").exists()

    shutil.rmtree(upload_dir, ignore_errors=True)


def test_create_project_persists_project_details_and_status(client: TestClient) -> None:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("README.md", "hello")

    create_response = client.post(
        "/api/projects",
        files={"file": ("repo.zip", archive_bytes.getvalue(), "application/zip")},
    )
    project_id = create_response.json()["project_id"]

    details_response = client.get(f"/api/projects/{project_id}")
    status_response = client.get(f"/api/projects/{project_id}/status")

    assert details_response.status_code == 200
    assert details_response.json()["display_name"] == "repo.zip"
    assert details_response.json()["status"] == "ready_to_index"
    assert status_response.status_code == 200
    assert status_response.json() == {
        "id": project_id,
        "status": "ready_to_index",
        "file_count": 0,
        "chunk_count": 0,
        "error_message": None,
    }

    shutil.rmtree(Path(settings.repolens_data_dir) / "uploads" / project_id, ignore_errors=True)


def test_create_project_rejects_non_zip_extension(client: TestClient) -> None:
    response = client.post(
        "/api/projects",
        files={"file": ("repo.txt", b"not-a-zip", "text/plain")},
    )

    assert response.status_code == 400
    assert "ZIP" in response.json()["detail"].upper()


def test_list_projects_returns_created_project(client: TestClient) -> None:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("README.md", "hello")

    create_response = client.post(
        "/api/projects",
        files={"file": ("repo.zip", archive_bytes.getvalue(), "application/zip")},
    )

    assert create_response.status_code == 201
    project_id = create_response.json()["project_id"]

    list_response = client.get("/api/projects")

    assert list_response.status_code == 200
    projects = list_response.json()
    assert any(project["id"] == project_id for project in projects)

    shutil.rmtree(Path(settings.repolens_data_dir) / "uploads" / project_id, ignore_errors=True)


def test_create_project_rejects_oversized_upload(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "repolens_max_upload_mb", 0)

    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("README.md", "hello")

    response = client.post(
        "/api/projects",
        files={"file": ("repo.zip", archive_bytes.getvalue(), "application/zip")},
    )

    assert response.status_code == 400
    assert "size" in response.json()["detail"].lower()


def test_create_project_rejects_path_traversal_in_archive(client: TestClient) -> None:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("../evil.txt", "oops")
    response = client.post(
        "/api/projects",
        files={"file": ("repo.zip", archive_bytes.getvalue(), "application/zip")},
    )

    assert response.status_code == 400
    assert "path" in response.json()["detail"].lower()


def test_create_project_rejects_invalid_zip(client: TestClient) -> None:
    response = client.post(
        "/api/projects",
        files={"file": ("repo.zip", b"not-a-zip", "application/zip")},
    )

    assert response.status_code == 400
    assert "valid zip" in response.json()["detail"].lower()


def test_create_project_rejects_symbolic_links(client: TestClient) -> None:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        symlink = zipfile.ZipInfo("linked-file")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(symlink, "target.txt")

    response = client.post(
        "/api/projects",
        files={"file": ("repo.zip", archive_bytes.getvalue(), "application/zip")},
    )

    assert response.status_code == 400
    assert "symbolic link" in response.json()["detail"].lower()


def test_project_endpoints_return_not_found_for_unknown_id(client: TestClient) -> None:
    assert client.get("/api/projects/missing").status_code == 404
    assert client.get("/api/projects/missing/status").status_code == 404


def test_projects_endpoint_allows_local_vite_origin(client: TestClient) -> None:
    response = client.get(
        "/api/projects",
        headers={"Origin": "http://127.0.0.1:5173"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_create_project_skips_excluded_directories(client: TestClient) -> None:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("src/app.py", "print('ok')")
        archive.writestr("node_modules/pkg/index.js", "console.log('skip')")
    response = client.post(
        "/api/projects",
        files={"file": ("repo.zip", archive_bytes.getvalue(), "application/zip")},
    )

    assert response.status_code == 201
    body = response.json()
    upload_dir = Path(settings.repolens_data_dir) / "uploads" / body["project_id"] / "extracted"
    assert (upload_dir / "src" / "app.py").exists()
    assert not (upload_dir / "node_modules").exists()

    shutil.rmtree(upload_dir.parent, ignore_errors=True)


def test_index_project_persists_chunks_and_exposes_source(client: TestClient) -> None:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr(
            "src/app.py",
            '"""Example module."""\n\n'
            "def greet(name):\n"
            '    return f"Hello {name}"\n',
        )
        archive.writestr(
            "README.md",
            "# Example\n\n"
            "Call `greet` to greet a user.\n",
        )
        archive.writestr("notes.txt", "unsupported")

    create_response = client.post(
        "/api/projects",
        files={"file": ("example.zip", archive_bytes.getvalue(), "application/zip")},
    )
    project_id = create_response.json()["project_id"]

    index_response = client.post(f"/api/projects/{project_id}/index")

    assert index_response.status_code == 202
    assert index_response.json() == {
        "project_id": project_id,
        "status": "indexing",
    }

    project = client.get(f"/api/projects/{project_id}").json()
    assert project["status"] == "indexed"
    assert project["file_count"] == 2
    assert project["chunk_count"] == 3

    chunks = ChunkRepository().list_for_project(project_id)
    assert len(chunks) == 3
    assert all(chunk["embedding_json"] == "[]" for chunk in chunks)

    chunk_list_response = client.get(f"/api/projects/{project_id}/chunks")
    assert chunk_list_response.status_code == 200
    assert len(chunk_list_response.json()) == 3

    function_chunk = next(
        chunk for chunk in chunks if chunk["symbol_name"] == "greet"
    )
    source_response = client.get(
        f"/api/projects/{project_id}/chunks/{function_chunk['id']}"
    )

    assert source_response.status_code == 200
    assert source_response.json() == {
        "chunk_id": function_chunk["id"],
        "file_path": "src/app.py",
        "language": "python",
        "symbol_name": "greet",
        "symbol_type": "function",
        "start_line": 3,
        "end_line": 4,
        "parse_status": "parsed",
        "score": None,
        "snippet": 'def greet(name):\n    return f"Hello {name}"',
    }


def test_reindex_replaces_existing_chunks(client: TestClient) -> None:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("app.py", "def run():\n    return True\n")

    create_response = client.post(
        "/api/projects",
        files={"file": ("example.zip", archive_bytes.getvalue(), "application/zip")},
    )
    project_id = create_response.json()["project_id"]

    assert client.post(f"/api/projects/{project_id}/index").status_code == 202
    first_chunks = ChunkRepository().list_for_project(project_id)
    assert client.post(f"/api/projects/{project_id}/index").status_code == 202
    second_chunks = ChunkRepository().list_for_project(project_id)

    assert len(first_chunks) == 1
    assert len(second_chunks) == 1


def test_index_and_chunk_endpoints_reject_unknown_resources(
    client: TestClient,
) -> None:
    assert client.post("/api/projects/missing/index").status_code == 404

    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("README.md", "# Example")
    create_response = client.post(
        "/api/projects",
        files={"file": ("example.zip", archive_bytes.getvalue(), "application/zip")},
    )
    project_id = create_response.json()["project_id"]

    response = client.get(f"/api/projects/{project_id}/chunks/missing")
    assert response.status_code == 404
