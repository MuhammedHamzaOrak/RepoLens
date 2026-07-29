import sqlite3
from pathlib import Path

from app.core.config import settings


def _get_database_path() -> Path:
    database_path = Path(settings.repolens_data_dir).expanduser().resolve() / "repolens.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return database_path


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_get_database_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                indexed_at TEXT,
                file_count INTEGER NOT NULL DEFAULT 0,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                error_message TEXT
            )
            """
        )

        # Keep existing local project records usable when upgrading from the
        # initial Phase 1 table, which persisted `name` only.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(projects)")}
        migrations = {
            "display_name": "ALTER TABLE projects ADD COLUMN display_name TEXT",
            "indexed_at": "ALTER TABLE projects ADD COLUMN indexed_at TEXT",
            "file_count": "ALTER TABLE projects ADD COLUMN file_count INTEGER NOT NULL DEFAULT 0",
            "chunk_count": "ALTER TABLE projects ADD COLUMN chunk_count INTEGER NOT NULL DEFAULT 0",
            "error_message": "ALTER TABLE projects ADD COLUMN error_message TEXT",
        }
        for column, statement in migrations.items():
            if column not in columns:
                conn.execute(statement)

        if "name" in columns:
            conn.execute(
                "UPDATE projects SET display_name = name WHERE display_name IS NULL"
            )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                file_path TEXT NOT NULL,
                language TEXT NOT NULL,
                symbol_name TEXT,
                symbol_type TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                parse_status TEXT NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunks_project_id ON chunks(project_id)"
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chunks_project_file
            ON chunks(project_id, file_path)
            """
        )
        conn.commit()


init_db()
