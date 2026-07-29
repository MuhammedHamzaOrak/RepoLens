from pathlib import Path

import pytest

from app.core.config import settings
from app.parsers.markdown_parser import MarkdownParser
from app.parsers.python_parser import PythonParser
from app.services.ingestion_service import IngestionService


def test_python_parser_chunks_module_function_class_and_method() -> None:
    source = '''"""Module docs."""
import os

def top_level():
    return os.name

class Greeter:
    """Greets a user."""
    prefix = "Hello"

    def hello(self, name):
        return f"{self.prefix} {name}"
'''

    chunks = PythonParser().parse("src/example.py", source)
    by_type = {chunk.symbol_type: chunk for chunk in chunks}

    assert by_type["module"].start_line == 1
    assert by_type["module"].end_line == 2
    assert by_type["function"].symbol_name == "top_level"
    assert (by_type["function"].start_line, by_type["function"].end_line) == (4, 5)
    assert by_type["class"].symbol_name == "Greeter"
    assert (by_type["class"].start_line, by_type["class"].end_line) == (7, 10)
    assert by_type["method"].symbol_name == "Greeter.hello"
    assert (by_type["method"].start_line, by_type["method"].end_line) == (11, 12)
    assert "class Greeter:" in by_type["method"].content
    assert "def hello" in by_type["method"].content


def test_python_parser_uses_fallback_for_syntax_errors() -> None:
    chunks = PythonParser().parse(
        "broken.py",
        "def broken(:\n    return True\n",
    )

    assert len(chunks) == 1
    assert chunks[0].parse_status == "fallback"
    assert chunks[0].symbol_type == "fallback"
    assert (chunks[0].start_line, chunks[0].end_line) == (1, 2)


def test_markdown_parser_preserves_heading_hierarchy_and_lines() -> None:
    source = """Intro text.
# Guide
Overview.
## Setup
Install it.
# API
Reference.
"""

    chunks = MarkdownParser().parse("README.md", source)

    assert [(chunk.symbol_name, chunk.start_line, chunk.end_line) for chunk in chunks] == [
        (None, 1, 1),
        ("Guide", 2, 3),
        ("Guide > Setup", 4, 5),
        ("API", 6, 7),
    ]


def test_ingestion_discovers_only_safe_supported_files(
    workspace_tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "repolens_max_source_file_kb", 1)
    (workspace_tmp_path / "src").mkdir()
    (workspace_tmp_path / "node_modules").mkdir()
    (workspace_tmp_path / "src" / "app.py").write_text(
        "def run():\n    return True\n",
        encoding="utf-8",
    )
    (workspace_tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    (workspace_tmp_path / "notes.txt").write_text("skip", encoding="utf-8")
    (workspace_tmp_path / "node_modules" / "hidden.py").write_text(
        "print('skip')",
        encoding="utf-8",
    )
    (workspace_tmp_path / "secret.py").write_text(
        'api_key = "abcdefghijklmnopqrstuvwxyz"\n',
        encoding="utf-8",
    )
    (workspace_tmp_path / "large.md").write_text("x" * 2048, encoding="utf-8")

    documents = IngestionService().discover(workspace_tmp_path)

    assert [document.file_path for document in documents] == [
        "README.md",
        "src/app.py",
    ]
    assert [document.language for document in documents] == ["markdown", "python"]
