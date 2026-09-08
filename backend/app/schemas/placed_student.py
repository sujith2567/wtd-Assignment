from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

class PlacedStudentBase(BaseModel):
    student_name: str
    company_name: str
    role_title: str
    cgpa: Decimal
    domain: str
    talents: Optional[List[str]] = []
    placement_year: int = 2024
    outcome: str = "PLACED"
    raw_resume_text: Optional[str] = None

class PlacedStudentCreate(PlacedStudentBase):
    pass

class PlacedStudentResponse(PlacedStudentBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
