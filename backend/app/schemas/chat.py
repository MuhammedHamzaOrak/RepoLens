from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.source import SourceResponse


MAX_CHAT_HISTORY_MESSAGES = 6
MAX_CHAT_MESSAGE_CHARS = 2000


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=MAX_CHAT_MESSAGE_CHARS)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("history content must not be blank")
        return stripped


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_CHAT_MESSAGE_CHARS)
    top_k: int | None = Field(default=None, ge=1, le=20)
    history: list[ChatHistoryMessage] = Field(
        default_factory=list,
        max_length=MAX_CHAT_HISTORY_MESSAGES,
    )

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
