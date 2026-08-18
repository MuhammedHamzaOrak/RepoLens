import argparse
import io
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
SUPPORTED_SUFFIXES = {".py", ".md", ".mdx"}
EXCLUDED_DIRECTORIES = {
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
    "data",
    "output",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run repeatable RepoLens retrieval and grounded-chat evaluation."
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=REPOSITORY_ROOT,
        help="Repository directory to package and evaluate.",
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=REPOSITORY_ROOT / "evaluation" / "questions.json",
        help="JSON question-set path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "evaluation" / "results" / "latest.json",
        help="Where to write the JSON result.",
    )
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--source-url", default=None)
    parser.add_argument("--source-commit", default=None)
    parser.add_argument(
        "--chat",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Call the chat endpoint in addition to retrieval.",
    )
    return parser.parse_args()


def build_archive(project_dir: Path) -> bytes:
    project_dir = project_dir.resolve()
    if not project_dir.is_dir():
        raise FileNotFoundError(f"Project directory does not exist: {project_dir}")

    archive_bytes = io.BytesIO()
    included_files = 0
    with zipfile.ZipFile(archive_bytes, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(project_dir.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(project_dir)
            if any(part in EXCLUDED_DIRECTORIES for part in relative.parts[:-1]):
                continue
            if path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            if path.stat().st_size > 512 * 1024:
                continue
            archive.write(path, relative.as_posix())
            included_files += 1

    if included_files == 0:
        raise ValueError("Project has no supported Python or Markdown files.")
    return archive_bytes.getvalue()


def load_questions(path: Path) -> list[dict[str, Any]]:
    questions = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(questions, list) or not questions:
        raise ValueError("Question set must be a non-empty JSON array.")

    seen_ids: set[str] = set()
    for item in questions:
        if not isinstance(item, dict):
            raise ValueError("Each question must be a JSON object.")
        question_id = item.get("id")
        category = item.get("category")
        if not isinstance(question_id, str) or not question_id:
            raise ValueError("Each question requires a non-empty id.")
        if question_id in seen_ids:
            raise ValueError(f"Duplicate question id: {question_id}")
        if category not in {"answerable", "unanswerable", "edge"}:
            raise ValueError(f"Unsupported category for {question_id}: {category}")
        seen_ids.add(question_id)
    return questions


def source_matches(source: dict[str, Any], question: dict[str, Any]) -> bool:
    expected_sources = question.get("expected_sources")
    if expected_sources:
        for expected in expected_sources:
            if source.get("file_path") != expected.get("file_path"):
                continue
            symbols = expected.get("symbol_names", [])
            if not symbols or source.get("symbol_name") in symbols:
                return True
        return False

    expected_paths = question.get("expected_paths", [])
    expected_symbols = question.get("expected_symbols", [])
    path_matches = not expected_paths or source.get("file_path") in expected_paths
    symbol_matches = (
        not expected_symbols or source.get("symbol_name") in expected_symbols
    )
    return path_matches and symbol_matches


def compact_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "file_path": source["file_path"],
            "symbol_name": source.get("symbol_name"),
            "start_line": source["start_line"],
            "end_line": source["end_line"],
            "score": source.get("score"),
        }
        for source in sources
    ]


def timed_post(client: Any, url: str, payload: dict[str, Any]) -> tuple[Any, float]:
    started_at = time.perf_counter()
    response = client.post(url, json=payload)
    duration_ms = (time.perf_counter() - started_at) * 1000
    return response, round(duration_ms, 2)


def create_project(client: Any, archive_bytes: bytes, filename: str) -> str:
    response = client.post(
        "/api/projects",
        files={"file": (filename, archive_bytes, "application/zip")},
    )
    response.raise_for_status()
    return response.json()["project_id"]


def evaluate_question(
    client: Any,
    indexed_project_id: str,
    unindexed_project_id: str,
    item: dict[str, Any],
    include_chat: bool,
) -> dict[str, Any]:
    category = item["category"]
    question = item.get("question", "")
    result: dict[str, Any] = {
        "id": item["id"],
        "category": category,
        "question": question,
    }

    if category == "edge":
        project_id = (
            unindexed_project_id
            if item.get("project_state") == "unindexed"
            else indexed_project_id
        )
        payload: dict[str, Any] = {"question": question}
        if "top_k" in item:
            payload["top_k"] = item["top_k"]
        response, duration_ms = timed_post(
            client,
            f"/api/projects/{project_id}/chat",
            payload,
        )
        body = response.json()
        expected_http = item["expected_http_status"]
        expected_status = item.get("expected_answer_status")
        result.update(
            {
                "http_status": response.status_code,
                "answer_status": body.get("answer_status"),
                "duration_ms": duration_ms,
                "passed": response.status_code == expected_http
                and (
                    expected_status is None
                    or body.get("answer_status") == expected_status
                ),
            }
        )
        return result

    search_response, retrieval_ms = timed_post(
        client,
        f"/api/projects/{indexed_project_id}/search",
        {"query": question, "top_k": item.get("top_k", 4)},
    )
    search_response.raise_for_status()
    search_body = search_response.json()
    search_sources = search_body["results"]
    retrieval_hit = any(source_matches(source, item) for source in search_sources)
    result.update(
        {
            "retrieval_status": search_body["status"],
            "retrieval_ms": retrieval_ms,
            "retrieval_hit": retrieval_hit if category == "answerable" else None,
            "retrieval_sources": compact_sources(search_sources),
        }
    )

    if include_chat:
        chat_response, chat_ms = timed_post(
            client,
            f"/api/projects/{indexed_project_id}/chat",
            {"question": question, "top_k": item.get("top_k", 4)},
        )
        chat_body = chat_response.json()
        chat_sources = chat_body.get("sources", [])
        result.update(
            {
                "chat_http_status": chat_response.status_code,
                "answer_status": chat_body.get("answer_status"),
                "chat_ms": chat_ms,
                "citation_hit": any(
                    source_matches(source, item) for source in chat_sources
                )
                if category == "answerable"
                else None,
                "chat_sources": compact_sources(chat_sources),
                "answer_preview": str(chat_body.get("answer", ""))[:500],
            }
        )

    if category == "answerable":
        result["passed"] = retrieval_hit and (
            not include_chat
            or (
                result.get("chat_http_status") == 200
                and result.get("answer_status") == "grounded"
                and result.get("citation_hit") is True
            )
        )
    else:
        result["passed"] = search_body["status"] == "insufficient_context" and (
            not include_chat
            or (
                result.get("chat_http_status") == 200
                and result.get("answer_status") == "insufficient_context"
                and not result.get("chat_sources")
            )
        )
    return result


def percentage(numerator: int, denominator: int) -> float:
    return round((numerator / denominator) * 100, 1) if denominator else 0.0


def build_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [result for result in results if result["category"] == "answerable"]
    unanswerable = [
        result for result in results if result["category"] == "unanswerable"
    ]
    edge = [result for result in results if result["category"] == "edge"]
    retrieval_times = [
        result["retrieval_ms"]
        for result in results
        if "retrieval_ms" in result
    ]
    chat_times = [result["chat_ms"] for result in results if "chat_ms" in result]
    retrieval_hits = sum(result.get("retrieval_hit") is True for result in answerable)
    citation_results = [
        result for result in answerable if "citation_hit" in result
    ]
    citation_hits = sum(
        result.get("citation_hit") is True for result in citation_results
    )
    unsupported_successes = sum(result["passed"] for result in unanswerable)
    edge_successes = sum(result["passed"] for result in edge)

    return {
        "question_count": len(results),
        "answerable_count": len(answerable),
        "unanswerable_count": len(unanswerable),
        "edge_count": len(edge),
        "retrieval_hits": retrieval_hits,
        "retrieval_hit_rate_percent": percentage(retrieval_hits, len(answerable)),
        "citation_hits": citation_hits,
        "citation_evaluated_count": len(citation_results),
        "citation_hit_rate_percent": percentage(
            citation_hits,
            len(citation_results),
        )
        if citation_results
        else None,
        "unsupported_successes": unsupported_successes,
        "unsupported_success_rate_percent": percentage(
            unsupported_successes,
            len(unanswerable),
        ),
        "edge_successes": edge_successes,
        "edge_success_rate_percent": percentage(edge_successes, len(edge))
        if edge
        else None,
        "median_retrieval_ms": round(statistics.median(retrieval_times), 2)
        if retrieval_times
        else None,
        "median_chat_ms": round(statistics.median(chat_times), 2)
        if chat_times
        else None,
        "passed_count": sum(result["passed"] for result in results),
    }


def main() -> None:
    args = parse_args()
    project_dir = args.project_dir.resolve()
    questions = load_questions(args.questions.resolve())
    archive_bytes = build_archive(project_dir)

    test_data_root = BACKEND_ROOT / ".test-data"
    test_data_root.mkdir(parents=True, exist_ok=True)
    data_dir = Path(tempfile.mkdtemp(prefix="repolens-evaluation-", dir=test_data_root))
    os.environ["REPOLENS_DATA_DIR"] = str(data_dir)
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))

    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.main import app

    project_name = args.project_name or project_dir.name
    print(
        f"Evaluating {project_name}: {len(questions)} questions, "
        f"archive={len(archive_bytes) / 1024:.1f}KB",
        flush=True,
    )

    try:
        with TestClient(app) as client:
            indexed_project_id = create_project(
                client,
                archive_bytes,
                f"{project_name}.zip",
            )
            unindexed_project_id = create_project(
                client,
                archive_bytes,
                f"{project_name}-unindexed.zip",
            )

            indexing_started = time.perf_counter()
            index_response = client.post(
                f"/api/projects/{indexed_project_id}/index"
            )
            index_response.raise_for_status()
            indexing_ms = round((time.perf_counter() - indexing_started) * 1000, 2)
            project = client.get(
                f"/api/projects/{indexed_project_id}"
            ).json()
            if project["status"] != "indexed":
                raise RuntimeError(f"Indexing failed: {project}")
            print(
                f"Indexed {project['file_count']} files / {project['chunk_count']} chunks "
                f"in {indexing_ms:.0f}ms",
                flush=True,
            )

            results: list[dict[str, Any]] = []
            for item in questions:
                result = evaluate_question(
                    client=client,
                    indexed_project_id=indexed_project_id,
                    unindexed_project_id=unindexed_project_id,
                    item=item,
                    include_chat=args.chat,
                )
                results.append(result)
                print(
                    f"[{item['id']}] {'PASS' if result['passed'] else 'FAIL'} "
                    f"{item['category']} "
                    f"retrieval={result.get('retrieval_hit', '-')} "
                    f"citation={result.get('citation_hit', '-')}",
                    flush=True,
                )

        report = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project": {
                "name": project_name,
                "source_url": args.source_url,
                "source_commit": args.source_commit,
                "file_count": project["file_count"],
                "chunk_count": project["chunk_count"],
                "indexing_ms": indexing_ms,
            },
            "configuration": {
                "top_k": settings.repolens_top_k,
                "min_similarity": settings.repolens_min_similarity,
                "embedding_model": settings.foundry_embedding_model,
                "chat_model": settings.foundry_chat_model,
                "embedding_batch_size": settings.repolens_embedding_batch_size,
                "chat_enabled": args.chat,
            },
            "metrics": build_metrics(results),
            "results": results,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report["metrics"], indent=2), flush=True)
        print(f"Wrote {args.output}", flush=True)
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
