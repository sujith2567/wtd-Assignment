from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from backend.app.models.match import MatchTier, RecruiterStatus
from backend.app.schemas.student import StudentResponse

class MatchShortlistBase(BaseModel):
    job_id: int
    student_id: int
    overall_score: float
    semantic_similarity: float
    skill_match_score: float
    academic_score: float
    match_tier: MatchTier = MatchTier.STRICT_MATCH
    explainability_summary: Optional[Dict[str, Any]] = None
    recruiter_status: RecruiterStatus = RecruiterStatus.SUGGESTED
    admin_dispatched: bool = False

class MatchShortlistResponse(MatchShortlistBase):
    id: int
    created_at: datetime
    updated_at: datetime
    student: Optional[StudentResponse] = None
    
    model_config = ConfigDict(from_attributes=True)

class CandidateMatchItem(BaseModel):
    student_id: int
    user_id: int
    full_name: str
    email: str
    roll_number: str
    department: str
    cgpa: float
    active_backlogs: int
    skills: List[str]
    match_tier: str
    overall_score: float
    academic_score: float
    skill_match_score: float
    semantic_similarity: float
    domain_fit_score: float = 0.0
    score_breakdown: Dict[str, float] = {}
    matching_skills: List[str]
    missing_skills: List[str]
    reason: str

class JobMatchResults(BaseModel):
    job_id: int
    job_title: str
    min_cgpa: float
    max_backlogs: int
    required_skills: List[str]
    total_candidates_evaluated: int
    strict_matches_count: int
    buffer_matches_count: int
    matches: List[CandidateMatchItem]
