from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from backend.app.models.application import ApplicationStatus

class ApplicationCreate(BaseModel):
    job_id: Optional[int] = None
    company_name: str
    status: Optional[ApplicationStatus] = ApplicationStatus.APPLIED

class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus

class ApplicationResponse(BaseModel):
    id: int
    student_id: int
    job_id: Optional[int]
    company_name: str
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
