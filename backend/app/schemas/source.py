from pydantic import BaseModel


class SourceResponse(BaseModel):
    chunk_id: str
    file_path: str
    symbol_name: str | None = None
    start_line: int
    end_line: int
    score: float | None = None
    snippet: str
