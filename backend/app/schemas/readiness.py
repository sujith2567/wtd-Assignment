from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class QuestionOption(BaseModel):
    text: str
    points: int # 0 to 5

class ReadinessQuestionOut(BaseModel):
    id: int
    domain: str
    question_text: str
    category: str
    weight: int
    options: List[QuestionOption]

class AnswerItem(BaseModel):
    question_id: int
    selected_points: int # 0 to 5

class SubmissionCreate(BaseModel):
    domain: str
    answers: List[AnswerItem]

class ReadinessScoreOut(BaseModel):
    id: int
    student_id: int
    domain: str
    total_score_percent: float
    strong_areas: List[str]
    weak_areas: List[str]
    category_scores: Dict[str, float]
    created_at: datetime
