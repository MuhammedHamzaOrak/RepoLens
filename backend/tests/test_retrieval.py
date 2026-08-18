import math

import pytest

from app.core.config import settings
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


class InstructionAwareEmbeddingProvider:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("Retrieval must not re-embed stored documents.")

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        if text.startswith("Instruct: "):
            return [1.0, 0.0]
        return [-1.0, 0.0]


class OperationCanonicalEmbeddingProvider:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("Retrieval must not re-embed stored documents.")

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        if text.endswith("Query: How does this calculator perform addition?"):
            return [1.0, 0.0]
        return [-1.0, 0.0]


class OverviewCanonicalEmbeddingProvider:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("Retrieval must not re-embed stored documents.")

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        if text.endswith(
            "Query: What is the main purpose of this software project?"
        ):
            return [1.0, 0.0]
        return [-1.0, 0.0]


def _chunk(
    file_path: str,
    symbol_name: str,
    *,
    language: str = "python",
    symbol_type: str = "function",
) -> ChunkCandidate:
    return ChunkCandidate(
        file_path=file_path,
        language=language,
        symbol_name=symbol_name,
        symbol_type=symbol_type,
        start_line=1,
        end_line=2,
        parse_status="parsed",
        content=f"def {symbol_name}():\n    pass",
    )


def _unit_vector_with_cosine(score: float) -> list[float]:
    return [score, math.sqrt(1 - score**2)]


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


def test_code_location_query_prefers_implementation_over_nearby_test_match() -> None:
    project_repository = ProjectRepository()
    chunk_repository = ChunkRepository()
    project_id = "location-ranking-project"
    project_repository.create(project_id, "location.zip", "ready_to_index")
    chunk_repository.replace_for_project(
        project_id,
        [
            _chunk("tests/test_users.py", "test_create_user_endpoint"),
            _chunk("app/api/users.py", "create_user"),
        ],
        [
            _unit_vector_with_cosine(0.68),
            _unit_vector_with_cosine(0.64),
        ],
    )
    project_repository.mark_indexed(project_id, file_count=2, chunk_count=2)
    service = RetrievalService(
        project_repository=project_repository,
        chunk_repository=chunk_repository,
        embedding_provider=FixedQueryEmbeddingProvider([1.0, 0.0]),
    )

    result = service.search(
        project_id,
        "Which API endpoint creates a user?",
        top_k=1,
        min_similarity=0.5,
    )

    assert result.results[0].chunk["file_path"] == "app/api/users.py"
    assert result.results[0].score == pytest.approx(0.64)


def test_how_query_prefers_implementation_over_docs_and_setup_helpers() -> None:
    project_repository = ProjectRepository()
    chunk_repository = ChunkRepository()
    project_id = "how-ranking-project"
    project_repository.create(project_id, "calculator.zip", "ready_to_index")
    chunk_repository.replace_for_project(
        project_id,
        [
            _chunk(
                "README.md",
                "calculator",
                language="markdown",
                symbol_type="heading",
            ),
            _chunk("generator.py", "", symbol_type="module"),
            _chunk("setup.py", "read"),
        ],
        [
            _unit_vector_with_cosine(0.44),
            _unit_vector_with_cosine(0.38),
            _unit_vector_with_cosine(0.39),
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
        "Toplama işlemini nasıl yapıyor?",
        top_k=3,
        min_similarity=0.35,
    )

    assert result.results[0].chunk["file_path"] == "generator.py"
    assert [item.chunk["file_path"] for item in result.results] == ["generator.py"]
    assert result.strategy == "implementation"


def test_implementation_query_keeps_setup_when_it_is_the_only_code_source() -> None:
    project_repository = ProjectRepository()
    chunk_repository = ChunkRepository()
    project_id = "setup-only-project"
    project_repository.create(project_id, "setup-only.zip", "ready_to_index")
    chunk_repository.replace_for_project(
        project_id,
        [_chunk("setup.py", "install")],
        [[1.0, 0.0]],
    )
    project_repository.mark_indexed(project_id, file_count=1, chunk_count=1)
    service = RetrievalService(
        project_repository=project_repository,
        chunk_repository=chunk_repository,
        embedding_provider=FixedQueryEmbeddingProvider([1.0, 0.0]),
    )

    result = service.search(
        project_id,
        "How is the package installed?",
        min_similarity=0.5,
    )

    assert [item.chunk["file_path"] for item in result.results] == ["setup.py"]


def test_default_search_retries_with_instruction_for_borderline_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_repository = ProjectRepository()
    chunk_repository = ChunkRepository()
    project_id = "instruction-fallback-project"
    project_repository.create(project_id, "calculator.zip", "ready_to_index")
    chunk_repository.replace_for_project(
        project_id,
        [
            _chunk(
                "README.md",
                "calculator",
                language="markdown",
                symbol_type="heading",
            ),
            _chunk("generator.py", "generate_operations"),
            _chunk("setup.py", "setup"),
        ],
        [
            _unit_vector_with_cosine(0.44),
            _unit_vector_with_cosine(0.38),
            _unit_vector_with_cosine(0.30),
        ],
    )
    project_repository.mark_indexed(project_id, file_count=3, chunk_count=3)
    provider = InstructionAwareEmbeddingProvider()
    service = RetrievalService(
        project_repository=project_repository,
        chunk_repository=chunk_repository,
        embedding_provider=provider,
    )
    monkeypatch.setattr(settings, "repolens_min_similarity", 0.5)
    monkeypatch.setattr(settings, "repolens_fallback_accept_similarity", 0.42)
    monkeypatch.setattr(settings, "repolens_fallback_context_similarity", 0.35)

    result = service.search(project_id, "Toplama işlemini nasıl yapıyor?", top_k=4)

    assert result.status == "ok"
    assert [item.chunk["file_path"] for item in result.results] == ["generator.py"]
    assert len(provider.queries) == 2
    assert provider.queries[1].startswith(
        f"Instruct: {settings.repolens_implementation_query_instruction}"
    )
    assert provider.queries[1].endswith("Query: Toplama işlemini nasıl yapıyor?")


def test_instruction_fallback_rejects_when_best_source_is_below_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_repository = ProjectRepository()
    chunk_repository = ChunkRepository()
    project_id = "instruction-rejection-project"
    project_repository.create(project_id, "calculator.zip", "ready_to_index")
    chunk_repository.replace_for_project(
        project_id,
        [_chunk("README.md", "calculator")],
        [_unit_vector_with_cosine(0.41)],
    )
    project_repository.mark_indexed(project_id, file_count=1, chunk_count=1)
    service = RetrievalService(
        project_repository=project_repository,
        chunk_repository=chunk_repository,
        embedding_provider=InstructionAwareEmbeddingProvider(),
    )
    monkeypatch.setattr(settings, "repolens_min_similarity", 0.5)
    monkeypatch.setattr(settings, "repolens_fallback_accept_similarity", 0.42)
    monkeypatch.setattr(settings, "repolens_fallback_context_similarity", 0.35)

    result = service.search(project_id, "Spacecraft thrust calibration", top_k=4)

    assert result.status == "insufficient_context"
    assert result.results == []


@pytest.mark.parametrize(
    "question",
    [
        "Toplama işlemi nasıl yapılıyor?",
        "Toplama işlemi nasıl yapılır?",
        "Bu kod toplama işlemini nasıl yapıyor?",
        "Toplama işlemini nasıl yuapıor?",
    ],
)
def test_operation_paraphrases_retry_with_canonical_implementation_query(
    monkeypatch: pytest.MonkeyPatch,
    question: str,
) -> None:
    project_repository = ProjectRepository()
    chunk_repository = ChunkRepository()
    project_id = "operation-canonical-project"
    project_repository.create(project_id, "calculator.zip", "ready_to_index")
    chunk_repository.replace_for_project(
        project_id,
        [
            _chunk(
                "README.md",
                "calculator",
                language="markdown",
                symbol_type="heading",
            ),
            _chunk("generator.py", "", symbol_type="module"),
        ],
        [[0.0, 1.0], [1.0, 0.0]],
    )
    project_repository.mark_indexed(project_id, file_count=2, chunk_count=2)
    provider = OperationCanonicalEmbeddingProvider()
    service = RetrievalService(
        project_repository=project_repository,
        chunk_repository=chunk_repository,
        embedding_provider=provider,
    )
    monkeypatch.setattr(settings, "repolens_min_similarity", 0.5)
    monkeypatch.setattr(settings, "repolens_fallback_accept_similarity", 0.42)
    monkeypatch.setattr(settings, "repolens_fallback_context_similarity", 0.35)

    result = service.search(project_id, question, top_k=4)

    assert result.status == "ok"
    assert [item.chunk["file_path"] for item in result.results] == ["generator.py"]
    assert result.strategy == "implementation"
    assert provider.queries[-1].endswith(
        "Query: How does this calculator perform addition?"
    )


@pytest.mark.parametrize(
    "question",
    [
        "Proje ne üzerine kurulu?",
        "Proje hangi konu ile alakalı?",
        "Ne işe yarıyor bu proje?",
        "Projeyi özetler misin?",
        "Ne ise yariyor bu porje?",
        "What's this repository for?",
    ],
)
def test_project_overview_routes_to_readme_and_main_module(
    monkeypatch: pytest.MonkeyPatch,
    question: str,
) -> None:
    project_repository = ProjectRepository()
    chunk_repository = ChunkRepository()
    project_id = "project-overview"
    project_repository.create(project_id, "calculator.zip", "ready_to_index")
    chunk_repository.replace_for_project(
        project_id,
        [
            _chunk(
                "README.md",
                "Calculator",
                language="markdown",
                symbol_type="heading",
            ),
            _chunk("generator.py", "", symbol_type="module"),
            _chunk("setup.py", "", symbol_type="module"),
        ],
        [
            _unit_vector_with_cosine(0.37),
            _unit_vector_with_cosine(0.18),
            _unit_vector_with_cosine(0.27),
        ],
    )
    project_repository.mark_indexed(project_id, file_count=3, chunk_count=3)
    provider = OverviewCanonicalEmbeddingProvider()
    service = RetrievalService(
        project_repository=project_repository,
        chunk_repository=chunk_repository,
        embedding_provider=provider,
    )
    monkeypatch.setattr(settings, "repolens_min_similarity", 0.5)
    monkeypatch.setattr(settings, "repolens_fallback_accept_similarity", 0.42)
    monkeypatch.setattr(settings, "repolens_fallback_context_similarity", 0.35)

    result = service.search(project_id, question, top_k=4)

    assert result.status == "ok"
    assert result.strategy == "overview"
    assert [item.chunk["file_path"] for item in result.results] == [
        "README.md",
        "generator.py",
    ]
    assert provider.queries[-1].endswith(
        "Query: What is the main purpose of this software project?"
    )
    assert len(provider.queries) == 1


def test_project_overview_without_readme_uses_substantive_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_repository = ProjectRepository()
    chunk_repository = ChunkRepository()
    project_id = "module-only-overview"
    project_repository.create(project_id, "module-only.zip", "ready_to_index")
    chunk_repository.replace_for_project(
        project_id,
        [
            _chunk("app.py", "", symbol_type="module"),
            _chunk("tests/test_app.py", "", symbol_type="module"),
            _chunk("setup.py", "", symbol_type="module"),
        ],
        [
            _unit_vector_with_cosine(0.28),
            _unit_vector_with_cosine(0.35),
            _unit_vector_with_cosine(0.40),
        ],
    )
    project_repository.mark_indexed(project_id, file_count=3, chunk_count=3)
    provider = OverviewCanonicalEmbeddingProvider()
    service = RetrievalService(
        project_repository=project_repository,
        chunk_repository=chunk_repository,
        embedding_provider=provider,
    )
    monkeypatch.setattr(settings, "repolens_min_similarity", 0.5)
    monkeypatch.setattr(settings, "repolens_fallback_accept_similarity", 0.42)
    monkeypatch.setattr(settings, "repolens_fallback_context_similarity", 0.35)

    result = service.search(project_id, "Ne yapıyor bu proje?", top_k=4)

    assert result.status == "ok"
    assert result.strategy == "overview"
    assert [item.chunk["file_path"] for item in result.results] == ["app.py"]


@pytest.mark.parametrize(
    "question",
    [
        "Projedeki upload servisi ne işe yarıyor?",
        "Bu projenin README dosyası ne yapıyor?",
        "What does the upload service do in this project?",
    ],
)
def test_component_question_does_not_trigger_project_overview_fallback(
    monkeypatch: pytest.MonkeyPatch,
    question: str,
) -> None:
    project_repository = ProjectRepository()
    chunk_repository = ChunkRepository()
    project_id = "component-not-overview"
    project_repository.create(project_id, "component.zip", "ready_to_index")
    chunk_repository.replace_for_project(
        project_id,
        [
            _chunk(
                "README.md",
                "Overview",
                language="markdown",
                symbol_type="heading",
            )
        ],
        [[1.0, 0.0]],
    )
    project_repository.mark_indexed(project_id, file_count=1, chunk_count=1)
    provider = OverviewCanonicalEmbeddingProvider()
    service = RetrievalService(
        project_repository=project_repository,
        chunk_repository=chunk_repository,
        embedding_provider=provider,
    )
    monkeypatch.setattr(settings, "repolens_min_similarity", 0.5)
    monkeypatch.setattr(settings, "repolens_fallback_accept_similarity", 0.42)
    monkeypatch.setattr(settings, "repolens_fallback_context_similarity", 0.35)

    result = service.search(project_id, question, top_k=4)

    assert result.status == "insufficient_context"
    assert result.strategy == "implementation"
    assert not provider.queries[-1].endswith(
        "Query: What is the main purpose of this software project?"
    )


def test_implementation_query_does_not_treat_docs_only_match_as_code() -> None:
    project_repository = ProjectRepository()
    chunk_repository = ChunkRepository()
    project_id = "docs-only-implementation-project"
    project_repository.create(project_id, "docs.zip", "ready_to_index")
    chunk_repository.replace_for_project(
        project_id,
        [
            _chunk(
                "docs/demo.md",
                "Unsupported question",
                language="markdown",
                symbol_type="heading",
            )
        ],
        [[1.0, 0.0]],
    )
    project_repository.mark_indexed(project_id, file_count=1, chunk_count=1)
    service = RetrievalService(
        project_repository=project_repository,
        chunk_repository=chunk_repository,
        embedding_provider=FixedQueryEmbeddingProvider([1.0, 0.0]),
    )

    result = service.search(
        project_id,
        "Where is spacecraft thrust calibration implemented?",
    )

    assert result.status == "insufficient_context"
    assert result.results == []
    assert result.strategy == "implementation"


def test_contextual_query_uses_guarded_follow_up_thresholds() -> None:
    class ContextualEmbeddingProvider:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise AssertionError("Retrieval must not re-embed stored documents.")

        def embed_query(self, text: str) -> list[float]:
            self.queries.append(text)
            if text == "focused follow-up context":
                return [1.0, 0.0]
            return [-1.0, 0.0]

    project_repository = ProjectRepository()
    chunk_repository = ChunkRepository()
    project_id = "contextual-follow-up-project"
    project_repository.create(project_id, "calculator.zip", "ready_to_index")
    chunk_repository.replace_for_project(
        project_id,
        [_chunk("src/calculator.py", "calculate")],
        [_unit_vector_with_cosine(0.45)],
    )
    project_repository.mark_indexed(project_id, file_count=1, chunk_count=1)
    provider = ContextualEmbeddingProvider()
    service = RetrievalService(
        project_repository=project_repository,
        chunk_repository=chunk_repository,
        embedding_provider=provider,
    )

    without_history = service.search(
        project_id,
        "İşlemleri neye göre yapıyor?",
    )
    with_history = service.search(
        project_id,
        "İşlemleri neye göre yapıyor?",
        contextual_query="focused follow-up context",
    )

    assert without_history.status == "insufficient_context"
    assert with_history.status == "ok"
    assert with_history.results[0].chunk["symbol_name"] == "calculate"
    assert with_history.results[0].score == pytest.approx(0.45)
    assert "focused follow-up context" in provider.queries
