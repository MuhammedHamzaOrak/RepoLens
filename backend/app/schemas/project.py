from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    file_name: str = Field(..., min_length=1)


class ProjectSummary(BaseModel):
    id: str
    display_name: str
    status: str
