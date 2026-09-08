from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from datetime import datetime
from decimal import Decimal

# Student Project Schemas
class StudentProjectBase(BaseModel):
    title: str
    description: str
    tech_stack: Optional[List[str]] = []
    github_url: Optional[str] = None
    live_url: Optional[str] = None
    domain_tag: Optional[str] = None

class StudentProjectCreate(StudentProjectBase):
    pass

class StudentProjectResponse(StudentProjectBase):
    id: int
    student_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Student Profile Schemas
class StudentBase(BaseModel):
    roll_number: str
    department: str
    batch_year: int
    cgpa: Decimal
    active_backlogs: int = 0
    history_backlogs: int = 0
    phone: Optional[str] = None
    gender: Optional[str] = None
    skills: Optional[List[str]] = []
    raw_resume_text: Optional[str] = None

class StudentCreate(StudentBase):
    user_id: int

class StudentUpdate(BaseModel):
    full_name: Optional[str] = None
    roll_number: Optional[str] = None
    department: Optional[str] = None
    batch_year: Optional[int] = None
    cgpa: Optional[Decimal] = None
    active_backlogs: Optional[int] = None
    history_backlogs: Optional[int] = None
    phone: Optional[str] = None
    skills: Optional[List[str]] = None
    raw_resume_text: Optional[str] = None
    predicted_domain: Optional[str] = None


class StudentResponse(StudentBase):
    id: int
    user_id: int
    full_name: Optional[str] = None
    domain_label: Optional[str] = None
    predicted_domain: Optional[str] = None
    domain_confidence: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    projects: List[StudentProjectResponse] = []
    
    model_config = ConfigDict(from_attributes=True)

class ContributingFactor(BaseModel):
    feature: str
    weight: float
    description: str

class DomainPredictionResponse(BaseModel):
    student_id: int
    roll_number: str
    student_name: str
    predicted_domain: str
    confidence_score: float
    ground_truth_domain: Optional[str] = None
    is_correct: Optional[bool] = None
    class_probabilities: dict[str, float]
    explainability: List[ContributingFactor]
    model_version: str

class StudentBulkUploadResult(BaseModel):
    total_parsed: int
    successful_inserts: int
    failed_rows: List[dict] = []


# ----- Explainability dashboard schemas -------------------------------------

class StudentExplanationExplanationFactor(BaseModel):
    """A single keyword/skill with its per-instance attribution weight."""
    keyword: str
    weight: float
    direction: str  # "supports" | "weakly_supports" | "against"
    description: str


class StudentExplanationTopClass(BaseModel):
    domain: str
    probability: float


class StudentExplanationResponse(BaseModel):
    """Response payload for GET /api/v1/matching/student/{id}/explanation."""
    student_id: int
    roll_number: str
    student_name: str
    predicted_domain: str
    confidence_score: float
    ground_truth_domain: Optional[str] = None
    is_correct: Optional[bool] = None
    is_noisy_case: bool  # True if domain_label exists and != predicted_domain
    class_probabilities: List[StudentExplanationTopClass]
    top_contributing_factors: List[StudentExplanationExplanationFactor]
    human_readable_summary: str
    model_version: str
