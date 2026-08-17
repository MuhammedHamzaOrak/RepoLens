from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.source import SourceResponse


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped


class ChatResponse(BaseModel):
    answer: str
    answer_status: Literal[
        "grounded",
        "insufficient_context",
        "indexing_incomplete",
        "error",
    ]
    sources: list[SourceResponse] = Field(default_factory=list)
