from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    file_name: str = Field(..., min_length=1)


class ProjectSummary(BaseModel):
    id: str
    display_name: str
    status: str
    created_at: datetime
    indexed_at: datetime | None = None
    file_count: int = 0
    chunk_count: int = 0
    error_message: str | None = None


class ProjectCreated(BaseModel):
    project_id: str
    filename: str


class ProjectStatus(BaseModel):
    id: str
    status: str
    file_count: int = 0
    chunk_count: int = 0
    error_message: str | None = None


class IndexStartResponse(BaseModel):
    project_id: str
    status: str
