import logging
from pathlib import Path

from app.core.config import settings
from app.parsers.base import ChunkCandidate
from app.parsers.markdown_parser import MarkdownParser
from app.parsers.python_parser import PythonParser
from app.providers.embeddings import EmbeddingProvider
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.project_repository import ProjectRepository
from app.services.ingestion_service import IngestionService, SourceDocument

logger = logging.getLogger(__name__)


class ProjectNotFoundError(Exception):
    pass


class ProjectAlreadyIndexingError(Exception):
    pass


class IndexingService:
    def __init__(
        self,
        project_repository: ProjectRepository,
        chunk_repository: ChunkRepository,
        ingestion_service: IngestionService,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.project_repository = project_repository
        self.chunk_repository = chunk_repository
        self.ingestion_service = ingestion_service
        self.embedding_provider = embedding_provider
        self.python_parser = PythonParser()
        self.markdown_parser = MarkdownParser()

    def prepare(self, project_id: str) -> None:
        project = self.project_repository.get(project_id)
        if project is None:
            raise ProjectNotFoundError
        if project["status"] == "indexing":
            raise ProjectAlreadyIndexingError
        self.project_repository.mark_indexing(project_id)

    def run(self, project_id: str) -> None:
        try:
            extracted_root = (
                Path(settings.repolens_data_dir) / "uploads" / project_id / "extracted"
            )
            documents = self.ingestion_service.discover(extracted_root)
            chunks = [
                chunk
                for document in documents
                for chunk in self._parse_document(document)
            ]
            embeddings = self._embed_chunks(chunks)
            self.chunk_repository.replace_for_project(
                project_id,
                chunks,
                embeddings,
            )
            self.project_repository.mark_indexed(
                project_id=project_id,
                file_count=len(documents),
                chunk_count=len(chunks),
            )
        except FileNotFoundError:
            self.project_repository.mark_failed(
                project_id,
                "Extracted project files are missing.",
            )
        except Exception:
            logger.exception("Project indexing failed for project %s", project_id)
            self.project_repository.mark_failed(
                project_id,
                "Indexing failed. Check the backend logs for details.",
            )

    def _parse_document(self, document: SourceDocument) -> list[ChunkCandidate]:
        if document.language == "python":
            return self.python_parser.parse(document.file_path, document.content)
        return self.markdown_parser.parse(document.file_path, document.content)

    def _embed_chunks(self, chunks: list[ChunkCandidate]) -> list[list[float]]:
        if not chunks:
            return []

        batch_size = max(1, settings.repolens_embedding_batch_size)
        embeddings: list[list[float]] = []
        for offset in range(0, len(chunks), batch_size):
            batch = chunks[offset : offset + batch_size]
            texts = [self._embedding_text(chunk) for chunk in batch]
            batch_embeddings = self.embedding_provider.embed_documents(texts)
            if len(batch_embeddings) != len(batch):
                raise ValueError(
                    "Embedding provider returned an unexpected number of vectors."
                )
            embeddings.extend(batch_embeddings)
        return embeddings

    def _embedding_text(self, chunk: ChunkCandidate) -> str:
        metadata = [
            f"File: {chunk.file_path}",
            f"Type: {chunk.symbol_type}",
        ]
        if chunk.symbol_name:
            metadata.append(f"Symbol: {chunk.symbol_name}")
        return "\n".join([*metadata, "", chunk.content])
