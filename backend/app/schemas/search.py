from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.source import SourceResponse


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    min_similarity: float | None = Field(default=None, ge=-1.0, le=1.0)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        query = value.strip()
        if not query:
            raise ValueError("Query must not be empty.")
        return query


class SearchResponse(BaseModel):
    status: Literal["ok", "insufficient_context"]
    results: list[SourceResponse]
