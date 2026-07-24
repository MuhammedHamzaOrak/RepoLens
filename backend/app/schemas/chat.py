from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = 4


class ChatResponse(BaseModel):
    answer: str
    answer_status: str
    sources: list[dict[str, object]] = []
