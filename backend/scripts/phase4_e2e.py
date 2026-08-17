import io
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    test_data_root = BACKEND_DIR / ".test-data"
    test_data_root.mkdir(parents=True, exist_ok=True)
    data_dir = Path(
        tempfile.mkdtemp(prefix="repolens-phase4-", dir=test_data_root)
    )
    os.environ["REPOLENS_DATA_DIR"] = str(data_dir)

    from fastapi.testclient import TestClient

    from app.main import app
    from app.repositories.database import init_db

    init_db()

    try:
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w") as archive:
            archive.writestr(
                "src/users.py",
                "def register_user(email):\n"
                '    """Create a user record for the supplied email."""\n'
                "    return {'email': email}\n",
            )

        with TestClient(app) as client:
            created = client.post(
                "/api/projects",
                files={
                    "file": (
                        "phase4-smoke.zip",
                        archive_bytes.getvalue(),
                        "application/zip",
                    )
                },
            )
            created.raise_for_status()
            project_id = created.json()["project_id"]

            indexed = client.post(f"/api/projects/{project_id}/index")
            indexed.raise_for_status()
            status = client.get(f"/api/projects/{project_id}/status")
            status.raise_for_status()
            assert status.json()["status"] == "indexed", status.text

            chat = client.post(
                f"/api/projects/{project_id}/chat",
                json={
                    "question": "Where is user registration implemented?",
                    "top_k": 2,
                },
            )
            chat.raise_for_status()
            result = chat.json()
            assert result["answer_status"] == "grounded", result
            assert result["sources"], result
            expected_source = next(
                source
                for source in result["sources"]
                if source["file_path"] == "src/users.py"
                and source["symbol_name"] == "register_user"
            )

            source = client.get(
                f"/api/projects/{project_id}/chunks/{expected_source['chunk_id']}"
            )
            source.raise_for_status()
            assert source.json()["snippet"] == expected_source["snippet"]

            print("Phase 4 E2E passed")
            print(f"answer_status={result['answer_status']}")
            print(f"answer={result['answer']}")
            print(
                "source="
                f"{expected_source['file_path']}:"
                f"{expected_source['start_line']}-{expected_source['end_line']}"
            )
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
