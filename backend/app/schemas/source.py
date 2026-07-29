from pydantic import BaseModel


class SourceSummaryResponse(BaseModel):
    chunk_id: str
    file_path: str
    language: str
    symbol_name: str | None = None
    symbol_type: str
    start_line: int
    end_line: int
    parse_status: str


class SourceResponse(SourceSummaryResponse):
    score: float | None = None
    snippet: str
