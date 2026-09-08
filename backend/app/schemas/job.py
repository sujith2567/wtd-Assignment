from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from backend.app.models.job import JobStatus

class JobPostingBase(BaseModel):
    title: str
    target_domain: str
    description: str
    min_cgpa: Decimal = Decimal("6.00")
    max_backlogs_allowed: int = 0
    required_skills: List[str]
    preferred_skills: Optional[List[str]] = []
    salary_range: Optional[str] = None
    location: Optional[str] = None
    status: JobStatus = JobStatus.ACTIVE
    buffer_threshold_percent: float = 10.0

class JobPostingCreate(JobPostingBase):
    pass

class JobPostingUpdate(BaseModel):
    title: Optional[str] = None
    target_domain: Optional[str] = None
    description: Optional[str] = None
    min_cgpa: Optional[Decimal] = None
    max_backlogs_allowed: Optional[int] = None
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    salary_range: Optional[str] = None
    location: Optional[str] = None
    status: Optional[JobStatus] = None
    buffer_threshold_percent: Optional[float] = None

class JobPostingResponse(JobPostingBase):
    id: int
    company_id: int
    company_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
