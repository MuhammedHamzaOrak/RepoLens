from pathlib import Path

from app.core.config import settings
from app.providers.chat import FoundryLocalChatProvider
from app.providers.embeddings import FoundryLocalEmbeddingProvider
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.project_repository import ProjectRepository
from app.services.indexing_service import IndexingService
from app.services.ingestion_service import IngestionService
from app.services.rag_service import RagService
from app.services.retrieval_service import RetrievalService

project_repository = ProjectRepository()
chunk_repository = ChunkRepository()
embedding_provider = FoundryLocalEmbeddingProvider(settings.foundry_embedding_model)
chat_provider = FoundryLocalChatProvider(
    model_alias=settings.foundry_chat_model,
    max_tokens=settings.repolens_chat_max_tokens,
    temperature=settings.repolens_chat_temperature,
    frequency_penalty=settings.repolens_chat_frequency_penalty,
    random_seed=settings.repolens_chat_random_seed,
)
indexing_service = IndexingService(
    project_repository=project_repository,
    chunk_repository=chunk_repository,
    ingestion_service=IngestionService(),
    embedding_provider=embedding_provider,
)
retrieval_service = RetrievalService(
    project_repository=project_repository,
    chunk_repository=chunk_repository,
    embedding_provider=embedding_provider,
)
system_prompt = (
    Path(__file__).resolve().parents[1] / "prompts" / "grounded_answer.txt"
).read_text(encoding="utf-8")
rag_service = RagService(
    retrieval_service=retrieval_service,
    chat_provider=chat_provider,
    system_prompt=system_prompt,
    max_context_chars=settings.repolens_max_context_chars,
    implementation_context_chunks=settings.repolens_implementation_context_chunks,
)
