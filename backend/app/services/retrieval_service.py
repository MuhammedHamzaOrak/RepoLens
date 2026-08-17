import json
from dataclasses import dataclass

import numpy as np

from app.core.config import settings
from app.providers.embeddings import EmbeddingProvider
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.project_repository import ProjectRepository


class ProjectNotFoundError(Exception):
    pass


class ProjectNotIndexedError(Exception):
    pass


class InvalidStoredEmbeddingError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk: dict
    score: float


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    status: str
    results: list[RetrievedChunk]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    left_vector = np.asarray(left, dtype=np.float64)
    right_vector = np.asarray(right, dtype=np.float64)
    if left_vector.ndim != 1 or right_vector.ndim != 1:
        raise ValueError("Cosine similarity requires one-dimensional vectors.")
    if left_vector.size == 0 or left_vector.shape != right_vector.shape:
        raise ValueError("Cosine similarity requires equal, non-empty vectors.")
    if not np.isfinite(left_vector).all() or not np.isfinite(right_vector).all():
        raise ValueError("Cosine similarity requires finite vector values.")

    denominator = np.linalg.norm(left_vector) * np.linalg.norm(right_vector)
    if denominator == 0:
        return 0.0
    return float(np.dot(left_vector, right_vector) / denominator)


class RetrievalService:
    def __init__(
        self,
        project_repository: ProjectRepository,
        chunk_repository: ChunkRepository,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.project_repository = project_repository
        self.chunk_repository = chunk_repository
        self.embedding_provider = embedding_provider

    def search(
        self,
        project_id: str,
        query: str,
        top_k: int | None = None,
        min_similarity: float | None = None,
    ) -> RetrievalResult:
        project = self.project_repository.get(project_id)
        if project is None:
            raise ProjectNotFoundError
        if project["status"] != "indexed":
            raise ProjectNotIndexedError

        result_limit = top_k if top_k is not None else settings.repolens_top_k
        threshold = (
            min_similarity
            if min_similarity is not None
            else settings.repolens_min_similarity
        )
        if result_limit < 1:
            raise ValueError("top_k must be at least 1.")
        if not -1.0 <= threshold <= 1.0:
            raise ValueError("min_similarity must be between -1 and 1.")
        chunks = self.chunk_repository.list_for_project(project_id)
        if not chunks:
            return RetrievalResult(status="insufficient_context", results=[])

        query_embedding = self.embedding_provider.embed_query(query)
        if (
            not query_embedding
            or not np.isfinite(query_embedding).all()
            or np.linalg.norm(query_embedding) == 0
        ):
            raise InvalidStoredEmbeddingError

        ranked: list[RetrievedChunk] = []
        for chunk in chunks:
            embedding = self._load_embedding(chunk["embedding_json"])
            try:
                score = cosine_similarity(query_embedding, embedding)
            except ValueError as exc:
                raise InvalidStoredEmbeddingError from exc
            if score >= threshold:
                ranked.append(RetrievedChunk(chunk=chunk, score=score))

        ranked.sort(key=lambda item: item.score, reverse=True)
        results = ranked[:result_limit]
        return RetrievalResult(
            status="ok" if results else "insufficient_context",
            results=results,
        )

    def _load_embedding(self, embedding_json: str) -> list[float]:
        try:
            embedding = json.loads(embedding_json)
            if not isinstance(embedding, list) or not embedding:
                raise ValueError
            vector = [float(value) for value in embedding]
            if not np.isfinite(vector).all() or np.linalg.norm(vector) == 0:
                raise ValueError
            return vector
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise InvalidStoredEmbeddingError from exc
