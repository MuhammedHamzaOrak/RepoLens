import io
import shutil
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.main import app


@pytest.fixture(autouse=True)
def isolated_db() -> None:
    from app.repositories.database import get_connection, init_db

    with get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS projects")
        conn.commit()

    init_db()


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

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "repo.zip"
    assert body["project_id"]

    upload_dir = Path(settings.repolens_data_dir) / "uploads" / body["project_id"]
    assert (upload_dir / "source.zip").exists()

    shutil.rmtree(upload_dir, ignore_errors=True)


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

    assert create_response.status_code == 200
    project_id = create_response.json()["project_id"]

    list_response = client.get("/api/projects")

    assert list_response.status_code == 200
    projects = list_response.json()
    assert any(project["id"] == project_id for project in projects)


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


def test_create_project_skips_excluded_directories(client: TestClient) -> None:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("src/app.py", "print('ok')")
        archive.writestr("node_modules/pkg/index.js", "console.log('skip')")
    response = client.post(
        "/api/projects",
        files={"file": ("repo.zip", archive_bytes.getvalue(), "application/zip")},
    )

    assert response.status_code == 200
    body = response.json()
    upload_dir = Path(settings.repolens_data_dir) / "uploads" / body["project_id"] / "extracted"
    assert (upload_dir / "src" / "app.py").exists()
    assert not (upload_dir / "node_modules").exists()

    shutil.rmtree(upload_dir.parent, ignore_errors=True)
