import shutil
import stat
import uuid
import zipfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.api.dependencies import (
    chunk_repository,
    indexing_service,
    project_repository,
    retrieval_service,
)
from app.core.config import settings
from app.providers.embeddings import EmbeddingProviderError
from app.schemas.project import (
    IndexStartResponse,
    ProjectCreated,
    ProjectStatus,
    ProjectSummary,
)
from app.schemas.search import SearchRequest, SearchResponse
from app.schemas.source import SourceResponse, SourceSummaryResponse
from app.services.indexing_service import ProjectAlreadyIndexingError, ProjectNotFoundError
from app.services.retrieval_service import (
    InvalidStoredEmbeddingError,
    ProjectNotFoundError as RetrievalProjectNotFoundError,
    ProjectNotIndexedError,
)

router = APIRouter()

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

                if stat.S_ISLNK(member.external_attr >> 16):
                    raise HTTPException(status_code=400, detail="Archive contains a symbolic link.")

                normalized_name = member.filename.replace("\\", "/")
                if any(part in EXCLUDED_DIRS for part in normalized_name.split("/")):
                    continue

                safe_path = (target_dir / normalized_name).resolve()
                target_root = target_dir.resolve()
                if safe_path == target_root or target_root not in safe_path.parents:
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


@router.post("/projects", status_code=201, response_model=ProjectCreated)
def create_project(file: Annotated[UploadFile, File(...)]) -> ProjectCreated:
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

    project_repository.create(
        project_id=project_id,
        display_name=filename,
        status="ready_to_index",
    )

    return ProjectCreated(project_id=project_id, filename=filename)


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects() -> list[dict]:
    return project_repository.list()


@router.get("/projects/{project_id}", response_model=ProjectSummary)
def get_project(project_id: str) -> dict:
    project = project_repository.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.get("/projects/{project_id}/status", response_model=ProjectStatus)
def get_project_status(project_id: str) -> ProjectStatus:
    project = project_repository.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return ProjectStatus(
        id=project["id"],
        status=project["status"],
        file_count=project["file_count"],
        chunk_count=project["chunk_count"],
        error_message=project["error_message"],
    )


@router.post(
    "/projects/{project_id}/index",
    status_code=202,
    response_model=IndexStartResponse,
)
def index_project(
    project_id: str,
    background_tasks: BackgroundTasks,
) -> IndexStartResponse:
    try:
        indexing_service.prepare(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except ProjectAlreadyIndexingError as exc:
        raise HTTPException(status_code=409, detail="Project is already indexing.") from exc

    background_tasks.add_task(indexing_service.run, project_id)
    return IndexStartResponse(project_id=project_id, status="indexing")


@router.get(
    "/projects/{project_id}/chunks",
    response_model=list[SourceSummaryResponse],
)
def list_source_chunks(project_id: str) -> list[SourceSummaryResponse]:
    if project_repository.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    return [
        SourceSummaryResponse(
            chunk_id=chunk["id"],
            file_path=chunk["file_path"],
            language=chunk["language"],
            symbol_name=chunk["symbol_name"],
            symbol_type=chunk["symbol_type"],
            start_line=chunk["start_line"],
            end_line=chunk["end_line"],
            parse_status=chunk["parse_status"],
        )
        for chunk in chunk_repository.list_for_project(project_id)
    ]


@router.get(
    "/projects/{project_id}/chunks/{chunk_id}",
    response_model=SourceResponse,
)
def get_source_chunk(project_id: str, chunk_id: str) -> SourceResponse:
    if project_repository.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    chunk = chunk_repository.get(project_id, chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Source chunk not found.")

    return SourceResponse(
        chunk_id=chunk["id"],
        file_path=chunk["file_path"],
        language=chunk["language"],
        symbol_name=chunk["symbol_name"],
        symbol_type=chunk["symbol_type"],
        start_line=chunk["start_line"],
        end_line=chunk["end_line"],
        parse_status=chunk["parse_status"],
        snippet=chunk["content"],
    )


@router.post(
    "/projects/{project_id}/search",
    response_model=SearchResponse,
)
def search_project(
    project_id: str,
    request: SearchRequest,
) -> SearchResponse:
    try:
        retrieval = retrieval_service.search(
            project_id=project_id,
            query=request.query,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
        )
    except RetrievalProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found.") from exc
    except ProjectNotIndexedError as exc:
        raise HTTPException(
            status_code=409,
            detail="Project must be indexed before it can be searched.",
        ) from exc
    except EmbeddingProviderError as exc:
        raise HTTPException(
            status_code=503,
            detail="The local embedding model is unavailable.",
        ) from exc
    except InvalidStoredEmbeddingError as exc:
        raise HTTPException(
            status_code=500,
            detail="The stored index is invalid. Re-index the project.",
        ) from exc

    return SearchResponse(
        status=retrieval.status,
        results=[
            SourceResponse(
                chunk_id=item.chunk["id"],
                file_path=item.chunk["file_path"],
                language=item.chunk["language"],
                symbol_name=item.chunk["symbol_name"],
                symbol_type=item.chunk["symbol_type"],
                start_line=item.chunk["start_line"],
                end_line=item.chunk["end_line"],
                parse_status=item.chunk["parse_status"],
                score=item.score,
                snippet=item.chunk["content"],
            )
            for item in retrieval.results
        ],
    )
