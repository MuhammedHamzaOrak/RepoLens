import ast

from app.parsers.base import ChunkCandidate

FALLBACK_CHUNK_LINES = 80


def _node_start_line(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", [])
    decorator_lines = [decorator.lineno for decorator in decorators]
    return min([node.lineno, *decorator_lines])


def _slice_lines(lines: list[str], start_line: int, end_line: int) -> str:
    return "\n".join(lines[start_line - 1 : end_line]).rstrip()


class PythonParser:
    def parse(self, file_path: str, source: str) -> list[ChunkCandidate]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return self._fallback_chunks(file_path, source)

        lines = source.splitlines()
        chunks: list[ChunkCandidate] = []
        chunks.extend(self._module_chunks(file_path, lines, tree))

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                chunks.append(
                    self._node_chunk(
                        file_path=file_path,
                        lines=lines,
                        node=node,
                        symbol_name=node.name,
                        symbol_type="function",
                    )
                )
            elif isinstance(node, ast.ClassDef):
                chunks.extend(self._class_chunks(file_path, lines, node))

        return [chunk for chunk in chunks if chunk.content.strip()]

    def _module_chunks(
        self,
        file_path: str,
        lines: list[str],
        tree: ast.Module,
    ) -> list[ChunkCandidate]:
        definition_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        groups: list[list[ast.stmt]] = []
        current_group: list[ast.stmt] = []

        for node in tree.body:
            if isinstance(node, definition_types):
                if current_group:
                    groups.append(current_group)
                    current_group = []
                continue
            current_group.append(node)

        if current_group:
            groups.append(current_group)

        chunks: list[ChunkCandidate] = []
        for group in groups:
            start_line = _node_start_line(group[0])
            end_line = group[-1].end_lineno or group[-1].lineno
            content = _slice_lines(lines, start_line, end_line)
            if content.strip():
                chunks.append(
                    ChunkCandidate(
                        file_path=file_path,
                        language="python",
                        symbol_name=None,
                        symbol_type="module",
                        start_line=start_line,
                        end_line=end_line,
                        parse_status="parsed",
                        content=content,
                    )
                )
        return chunks

    def _class_chunks(
        self,
        file_path: str,
        lines: list[str],
        node: ast.ClassDef,
    ) -> list[ChunkCandidate]:
        chunks: list[ChunkCandidate] = []
        class_start = _node_start_line(node)
        methods = [
            child
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        if methods:
            first_method_start = min(_node_start_line(method) for method in methods)
            class_end = max(class_start, first_method_start - 1)
        else:
            class_end = node.end_lineno or node.lineno

        class_content = _slice_lines(lines, class_start, class_end)
        if class_content.strip():
            chunks.append(
                ChunkCandidate(
                    file_path=file_path,
                    language="python",
                    symbol_name=node.name,
                    symbol_type="class",
                    start_line=class_start,
                    end_line=class_end,
                    parse_status="parsed",
                    content=class_content,
                )
            )

        class_header_end = node.body[0].lineno - 1 if node.body else node.lineno
        class_header = _slice_lines(lines, class_start, max(class_start, class_header_end))

        for method in methods:
            method_start = _node_start_line(method)
            method_end = method.end_lineno or method.lineno
            method_content = _slice_lines(lines, method_start, method_end)
            chunks.append(
                ChunkCandidate(
                    file_path=file_path,
                    language="python",
                    symbol_name=f"{node.name}.{method.name}",
                    symbol_type="method",
                    start_line=method_start,
                    end_line=method_end,
                    parse_status="parsed",
                    content=f"{class_header}\n{method_content}".rstrip(),
                )
            )

        return chunks

    def _node_chunk(
        self,
        file_path: str,
        lines: list[str],
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        symbol_name: str,
        symbol_type: str,
    ) -> ChunkCandidate:
        start_line = _node_start_line(node)
        end_line = node.end_lineno or node.lineno
        return ChunkCandidate(
            file_path=file_path,
            language="python",
            symbol_name=symbol_name,
            symbol_type=symbol_type,
            start_line=start_line,
            end_line=end_line,
            parse_status="parsed",
            content=_slice_lines(lines, start_line, end_line),
        )

    def _fallback_chunks(self, file_path: str, source: str) -> list[ChunkCandidate]:
        lines = source.splitlines()
        if not lines:
            return []

        chunks: list[ChunkCandidate] = []
        for offset in range(0, len(lines), FALLBACK_CHUNK_LINES):
            start_line = offset + 1
            end_line = min(offset + FALLBACK_CHUNK_LINES, len(lines))
            content = _slice_lines(lines, start_line, end_line)
            if content.strip():
                chunks.append(
                    ChunkCandidate(
                        file_path=file_path,
                        language="python",
                        symbol_name=None,
                        symbol_type="fallback",
                        start_line=start_line,
                        end_line=end_line,
                        parse_status="fallback",
                        content=content,
                    )
                )
        return chunks
