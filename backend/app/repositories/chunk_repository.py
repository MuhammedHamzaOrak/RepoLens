import hashlib
import json
import math
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from app.parsers.base import ChunkCandidate
from app.repositories.database import get_connection


class ChunkRepository:
    def replace_for_project(
        self,
        project_id: str,
        chunks: list[ChunkCandidate],
        embeddings: Sequence[Sequence[float]],
    ) -> list[str]:
        if len(chunks) != len(embeddings):
            raise ValueError("Each chunk must have exactly one embedding.")

        created_at = datetime.now(timezone.utc).isoformat()
        rows: list[tuple[object, ...]] = []
        chunk_ids: list[str] = []
        embedding_dimensions: int | None = None

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            chunk_id = str(uuid.uuid4())
            chunk_ids.append(chunk_id)
            vector = [float(value) for value in embedding]
            if not vector or not all(math.isfinite(value) for value in vector):
                raise ValueError("Chunk embeddings must contain finite numeric values.")
            if not any(value != 0.0 for value in vector):
                raise ValueError("Chunk embeddings must not be zero vectors.")
            if embedding_dimensions is None:
                embedding_dimensions = len(vector)
            elif len(vector) != embedding_dimensions:
                raise ValueError("Chunk embedding dimensions must be consistent.")
            rows.append(
                (
                    chunk_id,
                    project_id,
                    chunk.file_path,
                    chunk.language,
                    chunk.symbol_name,
                    chunk.symbol_type,
                    chunk.start_line,
                    chunk.end_line,
                    chunk.parse_status,
                    chunk.content,
                    hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                    json.dumps(vector),
                    created_at,
                )
            )

        with get_connection() as conn:
            conn.execute("DELETE FROM chunks WHERE project_id = ?", (project_id,))
            conn.executemany(
                """
                INSERT INTO chunks (
                    id, project_id, file_path, language, symbol_name,
                    symbol_type, start_line, end_line, parse_status, content,
                    content_hash, embedding_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()

        return chunk_ids

    def get(self, project_id: str, chunk_id: str) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, project_id, file_path, language, symbol_name,
                       symbol_type, start_line, end_line, parse_status, content,
                       content_hash, embedding_json, created_at
                FROM chunks
                WHERE project_id = ? AND id = ?
                """,
                (project_id, chunk_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def list_for_project(self, project_id: str) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, project_id, file_path, language, symbol_name,
                       symbol_type, start_line, end_line, parse_status, content,
                       content_hash, embedding_json, created_at
                FROM chunks
                WHERE project_id = ?
                ORDER BY file_path, start_line, id
                """,
                (project_id,),
            ).fetchall()
            return [dict(row) for row in rows]
