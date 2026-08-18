import json
import re
from dataclasses import dataclass

import numpy as np

from app.core.config import settings
from app.providers.embeddings import EmbeddingProvider
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.project_repository import ProjectRepository
from app.services.query_intent import (
    detect_operation,
    is_implementation_query,
    is_project_overview_query,
)


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
    strategy: str = "default"


GENERIC_SUPPORT_FILES = {
    "setup.py",
    "conftest.py",
}
IMPLEMENTATION_LANGUAGES = {"python"}
OVERVIEW_DOCUMENT_NAMES = {
    "readme.md",
    "readme.mdx",
}


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
        contextual_query: str | None = None,
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

        semantic_query = contextual_query or query
        prefer_overview = is_project_overview_query(query)
        prefer_implementation = self._is_code_location_query(query)
        if prefer_overview and min_similarity is None:
            ranked = self._overview_search(chunks)
        else:
            query_embedding = self.embedding_provider.embed_query(semantic_query)
            if (
                not query_embedding
                or not np.isfinite(query_embedding).all()
                or np.linalg.norm(query_embedding) == 0
            ):
                raise InvalidStoredEmbeddingError

            if contextual_query is not None and min_similarity is None:
                contextual_threshold = settings.repolens_fallback_context_similarity
                contextual_accept_threshold = (
                    settings.repolens_fallback_accept_similarity
                )
                ranked = self._score_chunks(
                    chunks,
                    query_embedding,
                    contextual_threshold,
                )
                if (
                    not ranked
                    or max(item.score for item in ranked)
                    < contextual_accept_threshold
                ):
                    ranked = []
            else:
                ranked = self._score_chunks(chunks, query_embedding, threshold)
            if prefer_implementation:
                ranked = self._implementation_chunks(ranked)

            if not ranked and min_similarity is None:
                ranked = self._fallback_search(
                    chunks,
                    semantic_query,
                    intent_query=query,
                )
                if prefer_implementation:
                    ranked = self._implementation_chunks(ranked)

            if (
                not ranked
                and min_similarity is None
                and prefer_implementation
                and (operation := detect_operation(query)) is not None
            ):
                canonical_query = (
                    f"How does this calculator perform {operation.english_name}?"
                )
                ranked = self._fallback_search(chunks, canonical_query)
                ranked = self._implementation_chunks(ranked)

        if prefer_overview:
            ranked.sort(key=self._overview_ranking_score, reverse=True)
        else:
            ranked.sort(
                key=lambda item: self._ranking_score(
                    item,
                    query,
                    prefer_implementation,
                ),
                reverse=True,
            )
        results = ranked[:result_limit]
        return RetrievalResult(
            status="ok" if results else "insufficient_context",
            results=results,
            strategy=(
                "overview"
                if prefer_overview
                else "implementation"
                if prefer_implementation
                else "default"
            ),
        )

    def _fallback_search(
        self,
        chunks: list[dict],
        query: str,
        intent_query: str | None = None,
    ) -> list[RetrievedChunk]:
        instruction = self._fallback_instruction(intent_query or query)
        if not instruction:
            return []

        accept_threshold = settings.repolens_fallback_accept_similarity
        context_threshold = settings.repolens_fallback_context_similarity
        if context_threshold > accept_threshold:
            raise ValueError(
                "Fallback context similarity must not exceed its accept similarity."
            )

        instructed_query = f"Instruct: {instruction}\nQuery: {query}"
        query_embedding = self.embedding_provider.embed_query(instructed_query)
        if (
            not query_embedding
            or not np.isfinite(query_embedding).all()
            or np.linalg.norm(query_embedding) == 0
        ):
            raise InvalidStoredEmbeddingError

        candidates = self._score_chunks(
            chunks,
            query_embedding,
            context_threshold,
        )
        if not candidates or max(item.score for item in candidates) < accept_threshold:
            return []
        return candidates

    def _implementation_chunks(
        self,
        candidates: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        implementation_candidates = [
            item
            for item in candidates
            if str(item.chunk.get("language", "")).casefold()
            in IMPLEMENTATION_LANGUAGES
        ]
        substantive_candidates = [
            item
            for item in implementation_candidates
            if self._file_name(item.chunk) not in GENERIC_SUPPORT_FILES
        ]
        return substantive_candidates or implementation_candidates

    def _overview_search(self, chunks: list[dict]) -> list[RetrievedChunk]:
        instruction = settings.repolens_query_instruction.strip()
        if not instruction:
            return []
        canonical_query = "What is the main purpose of this software project?"
        instructed_query = f"Instruct: {instruction}\nQuery: {canonical_query}"
        query_embedding = self.embedding_provider.embed_query(instructed_query)
        if (
            not query_embedding
            or not np.isfinite(query_embedding).all()
            or np.linalg.norm(query_embedding) == 0
        ):
            raise InvalidStoredEmbeddingError

        candidates = self._score_chunks(chunks, query_embedding, -1.0)
        overview_documents = [
            item for item in candidates if self._is_overview_document(item.chunk)
        ]
        substantive_modules = [
            item
            for item in candidates
            if str(item.chunk.get("language", "")).casefold()
            in IMPLEMENTATION_LANGUAGES
            and str(item.chunk.get("symbol_type", "")).casefold() == "module"
            and self._file_name(item.chunk) not in GENERIC_SUPPORT_FILES
            and not self._is_test_source(
                str(item.chunk.get("file_path", "")),
                str(item.chunk.get("symbol_name") or ""),
            )
        ]
        if overview_documents:
            return overview_documents + substantive_modules
        return substantive_modules or self._implementation_chunks(candidates)

    def _file_name(self, chunk: dict) -> str:
        file_path = str(chunk.get("file_path", "")).replace("\\", "/").casefold()
        return file_path.rsplit("/", maxsplit=1)[-1]

    def _is_overview_document(self, chunk: dict) -> bool:
        return self._file_name(chunk) in OVERVIEW_DOCUMENT_NAMES

    def _overview_ranking_score(self, item: RetrievedChunk) -> float:
        score = item.score
        if self._is_overview_document(item.chunk):
            score += 0.3
        if str(item.chunk.get("symbol_type", "")).casefold() == "module":
            score += 0.05
        return score

    def _fallback_instruction(self, query: str) -> str:
        if self._is_code_location_query(query):
            return settings.repolens_implementation_query_instruction.strip()
        return settings.repolens_query_instruction.strip()

    def _score_chunks(
        self,
        chunks: list[dict],
        query_embedding: list[float],
        threshold: float,
    ) -> list[RetrievedChunk]:
        ranked: list[RetrievedChunk] = []
        for chunk in chunks:
            embedding = self._load_embedding(chunk["embedding_json"])
            try:
                score = cosine_similarity(query_embedding, embedding)
            except ValueError as exc:
                raise InvalidStoredEmbeddingError from exc
            if score >= threshold:
                ranked.append(RetrievedChunk(chunk=chunk, score=score))
        return ranked

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

    def _is_code_location_query(self, query: str) -> bool:
        return is_implementation_query(query)

    def _ranking_score(
        self,
        item: RetrievedChunk,
        query: str,
        prefer_implementation: bool,
    ) -> float:
        if not prefer_implementation:
            return item.score

        chunk = item.chunk
        file_path = str(chunk.get("file_path", "")).replace("\\", "/").casefold()
        symbol_name = str(chunk.get("symbol_name") or "").casefold()
        symbol_type = str(chunk.get("symbol_type") or "").casefold()
        language = str(chunk.get("language") or "").casefold()
        score = item.score

        if language == "python":
            score += 0.04
        if symbol_type in {"function", "async_function", "method", "class"}:
            score += 0.025
        if self._is_test_source(file_path, symbol_name):
            score -= 0.08
        if language == "markdown":
            score -= 0.04
        if self._file_name(chunk) in GENERIC_SUPPORT_FILES:
            score -= 0.04

        lowered_query = query.casefold()
        if "endpoint" in lowered_query and "/api/" in f"/{file_path}":
            score += 0.15
        return score

    def _is_test_source(self, file_path: str, symbol_name: str) -> bool:
        path_parts = set(filter(None, re.split(r"[/_.-]+", file_path)))
        return (
            "tests" in path_parts
            or "test" in path_parts
            or symbol_name.startswith("test")
            or ".test" in symbol_name
        )
