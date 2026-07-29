import re
from dataclasses import dataclass

from app.parsers.base import ChunkCandidate

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True, slots=True)
class _Heading:
    line_index: int
    level: int
    title: str


class MarkdownParser:
    def parse(self, file_path: str, source: str) -> list[ChunkCandidate]:
        lines = source.splitlines()
        if not lines:
            return []

        headings = self._find_headings(lines)
        chunks: list[ChunkCandidate] = []

        if not headings:
            content = "\n".join(lines).rstrip()
            if content.strip():
                chunks.append(
                    self._chunk(
                        file_path=file_path,
                        symbol_name=None,
                        symbol_type="document",
                        start_line=1,
                        end_line=len(lines),
                        content=content,
                    )
                )
            return chunks

        first_heading_line = headings[0].line_index
        if first_heading_line > 0:
            preamble = "\n".join(lines[:first_heading_line]).rstrip()
            if preamble.strip():
                chunks.append(
                    self._chunk(
                        file_path=file_path,
                        symbol_name=None,
                        symbol_type="document",
                        start_line=1,
                        end_line=first_heading_line,
                        content=preamble,
                    )
                )

        hierarchy: dict[int, str] = {}
        for index, heading in enumerate(headings):
            hierarchy[heading.level] = heading.title
            for deeper_level in [level for level in hierarchy if level > heading.level]:
                del hierarchy[deeper_level]

            next_line_index = (
                headings[index + 1].line_index if index + 1 < len(headings) else len(lines)
            )
            content = "\n".join(lines[heading.line_index:next_line_index]).rstrip()
            symbol_name = " > ".join(
                hierarchy[level] for level in sorted(hierarchy) if level <= heading.level
            )
            chunks.append(
                self._chunk(
                    file_path=file_path,
                    symbol_name=symbol_name,
                    symbol_type="heading",
                    start_line=heading.line_index + 1,
                    end_line=next_line_index,
                    content=content,
                )
            )

        return [chunk for chunk in chunks if chunk.content.strip()]

    def _find_headings(self, lines: list[str]) -> list[_Heading]:
        headings: list[_Heading] = []
        for line_index, line in enumerate(lines):
            match = HEADING_PATTERN.match(line)
            if match:
                title = match.group(2).strip().rstrip("#").rstrip()
                headings.append(
                    _Heading(
                        line_index=line_index,
                        level=len(match.group(1)),
                        title=title,
                    )
                )
        return headings

    def _chunk(
        self,
        file_path: str,
        symbol_name: str | None,
        symbol_type: str,
        start_line: int,
        end_line: int,
        content: str,
    ) -> ChunkCandidate:
        return ChunkCandidate(
            file_path=file_path,
            language="markdown",
            symbol_name=symbol_name,
            symbol_type=symbol_type,
            start_line=start_line,
            end_line=end_line,
            parse_status="parsed",
            content=content,
        )
