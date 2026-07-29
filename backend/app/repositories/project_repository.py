from datetime import datetime, timezone

from app.repositories.database import get_connection


class ProjectRepository:
    def create(self, project_id: str, display_name: str, status: str) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, display_name, status, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (project_id, display_name, status, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def get(self, project_id: str) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, display_name, status, created_at, indexed_at,
                       file_count, chunk_count, error_message
                FROM projects WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def list(self) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, display_name, status, created_at, indexed_at,
                       file_count, chunk_count, error_message
                FROM projects
                ORDER BY created_at DESC
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def mark_indexing(self, project_id: str) -> bool:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE projects
                SET status = 'indexing', error_message = NULL
                WHERE id = ?
                """,
                (project_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def mark_indexed(self, project_id: str, file_count: int, chunk_count: int) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE projects
                SET status = 'indexed',
                    indexed_at = ?,
                    file_count = ?,
                    chunk_count = ?,
                    error_message = NULL
                WHERE id = ?
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    file_count,
                    chunk_count,
                    project_id,
                ),
            )
            conn.commit()

    def mark_failed(self, project_id: str, error_message: str) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE projects
                SET status = 'failed', error_message = ?
                WHERE id = ?
                """,
                (error_message, project_id),
            )
            conn.commit()
