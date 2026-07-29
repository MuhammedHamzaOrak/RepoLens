from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ChunkCandidate:
    file_path: str
    language: str
    symbol_name: str | None
    symbol_type: str
    start_line: int
    end_line: int
    parse_status: str
    content: str


class SourceParser(Protocol):
    def parse(self, file_path: str, source: str) -> list[ChunkCandidate]:
        ...
