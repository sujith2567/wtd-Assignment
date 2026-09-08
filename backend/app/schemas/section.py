from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class SectionCreate(BaseModel):
    name: str


class SectionResponse(BaseModel):
    id: int
    name: str
    created_by: Optional[int] = None
    created_at: datetime
    student_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class SectionListResponse(BaseModel):
    sections: List[SectionResponse]
    total: int


class SectionStudentAdd(BaseModel):
    student_id: int
