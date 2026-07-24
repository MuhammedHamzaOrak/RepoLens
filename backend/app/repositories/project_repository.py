from datetime import datetime, timezone

from app.repositories.database import get_connection


class ProjectRepository:
    def create(self, project_id: str, name: str, status: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, status, created_at) VALUES (?, ?, ?, ?)",
                (project_id, name, status, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def get(self, project_id: str) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, status, created_at FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def list(self) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, name, status, created_at FROM projects ORDER BY created_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]
