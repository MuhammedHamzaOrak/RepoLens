import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings

SUPPORTED_SUFFIXES = {".py": "python", ".md": "markdown", ".mdx": "markdown"}
EXCLUDED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".pytest_cache",
    "coverage",
    ".idea",
    ".vscode",
    "vendor",
}
SECRET_LIKE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "id_rsa",
    "id_ed25519",
}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    re.compile(
        r"""(?ix)
        \b(api[_-]?key|client[_-]?secret|password|access[_-]?token)\b
        \s*=\s*
        ["'][^"'\r\n]{16,}["']
        """
    ),
)


@dataclass(frozen=True, slots=True)
class SourceDocument:
    file_path: str
    language: str
    content: str


class IngestionService:
    def discover(self, root: Path) -> list[SourceDocument]:
        root = root.resolve()
        if not root.is_dir():
            raise FileNotFoundError("Extracted project files are missing.")

        documents: list[SourceDocument] = []
        for path in sorted(root.rglob("*")):
            if not self._is_candidate(root, path):
                continue

            try:
                content = path.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue

            if "\x00" in content or self._contains_likely_secret(content):
                continue

            relative_path = path.relative_to(root).as_posix()
            documents.append(
                SourceDocument(
                    file_path=relative_path,
                    language=SUPPORTED_SUFFIXES[path.suffix.lower()],
                    content=content,
                )
            )
        return documents

    def _is_candidate(self, root: Path, path: Path) -> bool:
        if not path.is_file() or path.is_symlink():
            return False

        try:
            relative_path = path.resolve().relative_to(root)
        except ValueError:
            return False

        if any(part in EXCLUDED_DIRECTORIES for part in relative_path.parts[:-1]):
            return False
        if path.name.lower() in SECRET_LIKE_NAMES:
            return False
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            return False

        max_bytes = settings.repolens_max_source_file_kb * 1024
        try:
            return path.stat().st_size <= max_bytes
        except OSError:
            return False

    def _contains_likely_secret(self, content: str) -> bool:
        return any(pattern.search(content) for pattern in SECRET_PATTERNS)
