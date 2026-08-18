import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from scripts.run_evaluation import (
    build_archive,
    build_metrics,
    load_questions,
    source_matches,
)


def test_phase_six_question_set_is_complete_and_points_to_existing_files() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    questions = load_questions(repository_root / "evaluation" / "questions.json")

    assert len(questions) == 20
    assert sum(item["category"] == "answerable" for item in questions) == 12
    assert sum(item["category"] == "unanswerable" for item in questions) == 4
    assert sum(item["category"] == "edge" for item in questions) == 4

    for item in questions:
        for expected_path in item.get("expected_paths", []):
            assert (repository_root / expected_path).is_file(), (
                f"{item['id']} points to a missing file: {expected_path}"
            )
        for expected_source in item.get("expected_sources", []):
            expected_path = expected_source["file_path"]
            assert (repository_root / expected_path).is_file(), (
                f"{item['id']} points to a missing file: {expected_path}"
            )


def test_recorded_phase_six_result_is_consistent_with_current_question_set() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    questions = load_questions(repository_root / "evaluation" / "questions.json")
    report = json.loads(
        (repository_root / "evaluation" / "results" / "latest.json").read_text(
            encoding="utf-8"
        )
    )
    results = report["results"]
    questions_by_id = {item["id"]: item for item in questions}

    assert [result["id"] for result in results] == [item["id"] for item in questions]
    assert report["metrics"] == build_metrics(results)
    assert all(result["passed"] for result in results)

    for result in results:
        if result["category"] != "answerable":
            continue
        question = questions_by_id[result["id"]]
        assert any(
            source_matches(source, question)
            for source in result["retrieval_sources"]
        )
        assert any(
            source_matches(source, question) for source in result["chat_sources"]
        )


def test_build_archive_includes_only_supported_safe_inputs(
    workspace_tmp_path: Path,
) -> None:
    (workspace_tmp_path / "src").mkdir()
    (workspace_tmp_path / "src" / "app.py").write_text(
        "def run():\n    pass\n",
        encoding="utf-8",
    )
    (workspace_tmp_path / "README.md").write_text("# Example\n", encoding="utf-8")
    (workspace_tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    (workspace_tmp_path / ".git").mkdir()
    (workspace_tmp_path / ".git" / "hidden.py").write_text(
        "ignored = True",
        encoding="utf-8",
    )

    archive = build_archive(workspace_tmp_path)

    with zipfile.ZipFile(BytesIO(archive)) as zip_file:
        assert sorted(zip_file.namelist()) == ["README.md", "src/app.py"]


def test_build_archive_rejects_a_project_without_supported_files(
    workspace_tmp_path: Path,
) -> None:
    (workspace_tmp_path / "notes.txt").write_text(
        "no supported files",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="no supported Python or Markdown files"):
        build_archive(workspace_tmp_path)


def test_source_match_requires_expected_path_and_symbol() -> None:
    source = {"file_path": "src/app.py", "symbol_name": "run"}
    question = {
        "expected_paths": ["src/app.py"],
        "expected_symbols": ["run"],
    }

    assert source_matches(source, question)
    assert not source_matches(
        {"file_path": "src/app.py", "symbol_name": "other"},
        question,
    )


def test_source_match_supports_path_specific_symbol_alternatives() -> None:
    question = {
        "expected_sources": [
            {
                "file_path": "src/service.py",
                "symbol_names": ["Service", "Service.run"],
            },
            {"file_path": "docs/service.md"},
        ]
    }

    assert source_matches(
        {"file_path": "src/service.py", "symbol_name": "Service.run"},
        question,
    )
    assert source_matches(
        {"file_path": "docs/service.md", "symbol_name": "Service"},
        question,
    )
    assert not source_matches(
        {"file_path": "src/other.py", "symbol_name": "Service.run"},
        question,
    )


def test_build_metrics_reports_rates_and_medians() -> None:
    results = [
        {
            "category": "answerable",
            "passed": True,
            "retrieval_hit": True,
            "citation_hit": True,
            "retrieval_ms": 10.0,
            "chat_ms": 100.0,
        },
        {
            "category": "answerable",
            "passed": False,
            "retrieval_hit": False,
            "citation_hit": False,
            "retrieval_ms": 30.0,
            "chat_ms": 300.0,
        },
        {"category": "unanswerable", "passed": True, "retrieval_ms": 20.0},
        {"category": "edge", "passed": True},
    ]

    metrics = build_metrics(results)

    assert metrics["retrieval_hit_rate_percent"] == 50.0
    assert metrics["citation_hit_rate_percent"] == 50.0
    assert metrics["unsupported_success_rate_percent"] == 100.0
    assert metrics["edge_success_rate_percent"] == 100.0
    assert metrics["median_retrieval_ms"] == 20.0
    assert metrics["median_chat_ms"] == 200.0
    assert metrics["passed_count"] == 3


def test_load_questions_rejects_duplicate_ids(workspace_tmp_path: Path) -> None:
    path = workspace_tmp_path / "questions.json"
    path.write_text(
        json.dumps(
            [
                {"id": "A01", "category": "answerable", "question": "One"},
                {"id": "A01", "category": "answerable", "question": "Two"},
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate question id"):
        load_questions(path)
