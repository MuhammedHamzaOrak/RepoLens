import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.repositories.project_repository import ProjectRepository

router = APIRouter()
project_repository = ProjectRepository()

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "coverage",
    "vendor",
}


def _safe_extract_zip(source_path: Path, target_dir: Path) -> None:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    max_bytes = settings.repolens_max_uncompressed_mb * 1024 * 1024
    max_files = settings.repolens_max_files
    total_written = 0
    file_count = 0

    try:
        with zipfile.ZipFile(source_path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue

                normalized_name = member.filename.replace("\\", "/")
                if any(part in EXCLUDED_DIRS for part in normalized_name.split("/")):
                    continue

                safe_path = (target_dir / normalized_name).resolve()
                target_root = target_dir.resolve()
                if safe_path != target_root and target_root not in safe_path.parents:
                    raise HTTPException(status_code=400, detail="Archive contains a path that escapes the extraction directory.")

                file_count += 1
                if file_count > max_files:
                    raise HTTPException(status_code=400, detail="Archive contains too many files.")

                member_size = member.file_size
                if total_written + member_size > max_bytes:
                    raise HTTPException(status_code=400, detail="Archive exceeds the maximum uncompressed size.")

                safe_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, safe_path.open("wb") as destination:
                    shutil.copyfileobj(source, destination)

                total_written += member_size
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid ZIP archive.") from exc


@router.post("/projects")
def create_project(file: Annotated[UploadFile, File(...)]) -> dict[str, str]:
    filename = file.filename or ""
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip uploads are supported.")

    max_bytes = settings.repolens_max_upload_mb * 1024 * 1024
    contents = file.file.read()
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds the maximum allowed size of {settings.repolens_max_upload_mb}MB.",
        )

    project_id = str(uuid.uuid4())
    target_dir = Path(settings.repolens_data_dir) / "uploads" / project_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "source.zip"
    target_path.write_bytes(contents)

    try:
        _safe_extract_zip(target_path, target_dir / "extracted")
    except HTTPException:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise

    project_repository.create(project_id=project_id, name=filename, status="extracted")

    return {"project_id": project_id, "filename": filename}


@router.get("/projects")
def list_projects() -> list[dict[str, str]]:
    return project_repository.list()
