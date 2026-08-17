import pytest

from app.parsers.base import ChunkCandidate
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.database import get_connection, init_db
from app.repositories.project_repository import ProjectRepository
from app.services.retrieval_service import RetrievalService, cosine_similarity


class FixedQueryEmbeddingProvider:
    def __init__(self, query_embedding: list[float]) -> None:
        self.query_embedding = query_embedding

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("Retrieval must not re-embed stored documents.")

    def embed_query(self, text: str) -> list[float]:
        return self.query_embedding


def _chunk(file_path: str, symbol_name: str) -> ChunkCandidate:
    return ChunkCandidate(
        file_path=file_path,
        language="python",
        symbol_name=symbol_name,
        symbol_type="function",
        start_line=1,
        end_line=2,
        parse_status="parsed",
        content=f"def {symbol_name}():\n    pass",
    )


def test_cosine_similarity_handles_ranked_orthogonal_and_zero_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_retrieval_ranks_results_and_applies_minimum_similarity() -> None:
    project_repository = ProjectRepository()
    chunk_repository = ChunkRepository()
    project_id = "retrieval-project"
    project_repository.create(project_id, "retrieval.zip", "ready_to_index")
    chunk_repository.replace_for_project(
        project_id,
        [
            _chunk("src/users.py", "register_user"),
            _chunk("src/payments.py", "charge_card"),
            _chunk("src/logging.py", "write_log"),
        ],
        [
            [1.0, 0.0],
            [0.8, 0.2],
            [-1.0, 0.0],
        ],
    )
    project_repository.mark_indexed(project_id, file_count=3, chunk_count=3)

    service = RetrievalService(
        project_repository=project_repository,
        chunk_repository=chunk_repository,
        embedding_provider=FixedQueryEmbeddingProvider([1.0, 0.0]),
    )

    result = service.search(
        project_id,
        "Where is registration?",
        top_k=2,
        min_similarity=0.5,
    )

    assert result.status == "ok"
    assert [item.chunk["symbol_name"] for item in result.results] == [
        "register_user",
        "charge_card",
    ]
    assert result.results[0].score == pytest.approx(1.0)

    unrelated_service = RetrievalService(
        project_repository=project_repository,
        chunk_repository=chunk_repository,
        embedding_provider=FixedQueryEmbeddingProvider([0.0, 1.0]),
    )
    insufficient = unrelated_service.search(
        project_id,
        "Where is deployment?",
        min_similarity=0.5,
    )
    assert insufficient.status == "insufficient_context"
    assert insufficient.results == []


def test_phase_two_placeholder_vectors_require_reindexing() -> None:
    project_repository = ProjectRepository()
    chunk_repository = ChunkRepository()
    project_id = "legacy-project"
    project_repository.create(project_id, "legacy.zip", "ready_to_index")
    chunk_repository.replace_for_project(
        project_id,
        [_chunk("legacy.py", "legacy")],
        [[1.0, 0.0]],
    )
    project_repository.mark_indexed(project_id, file_count=1, chunk_count=1)

    with get_connection() as connection:
        connection.execute(
            "UPDATE chunks SET embedding_json = '[]' WHERE project_id = ?",
            (project_id,),
        )
        connection.commit()

    init_db()

    project = project_repository.get(project_id)
    assert project is not None
    assert project["status"] == "ready_to_index"
    assert project["chunk_count"] == 0
    assert chunk_repository.list_for_project(project_id) == []
