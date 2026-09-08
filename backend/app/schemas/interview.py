from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from backend.app.models.interview import InterviewOutcome

class InterviewRecordBase(BaseModel):
    student_id: int
    job_id: int
    match_id: Optional[int] = None
    round_number: int = 1
    round_name: str = "Technical Round"
    technical_score: float
    communication_score: float
    problem_solving_score: float
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    detailed_feedback: Optional[str] = None
    interview_outcome: InterviewOutcome = InterviewOutcome.PASSED
    improvement_recommendations: Optional[List[str]] = []

class InterviewRecordCreate(InterviewRecordBase):
    pass

class InterviewRecordResponse(InterviewRecordBase):
    id: int
    student_name: Optional[str] = None
    student_roll: Optional[str] = None
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FeedbackSuggestionRequest(BaseModel):
    technical_score: float
    communication_score: float
    problem_solving_score: float
    outcome: str = "passed"

class FeedbackSuggestionResponse(BaseModel):
    suggested_strengths: str
    suggested_weaknesses: str
    suggested_summary: str
    recommendations: List[str]
