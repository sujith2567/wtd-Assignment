from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from backend.app.core.database import Base

class InterviewOutcome(str, enum.Enum):
    PASSED = "passed"
    FAILED = "failed"
    ON_HOLD = "on_hold"

class InterviewRecord(Base):
    __tablename__ = "interview_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("match_shortlists.id", ondelete="CASCADE"), nullable=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True)
    
    round_number = Column(Integer, default=1, nullable=False)
    round_name = Column(String(100), nullable=False)  # e.g., 'Technical Assessment', 'System Design'
    
    # Structured Feedback Metrics (1 to 10 scale)
    technical_score = Column(Float, nullable=False)
    communication_score = Column(Float, nullable=False)
    problem_solving_score = Column(Float, nullable=False)
    
    # Qualitative Feedback
    strengths = Column(Text, nullable=True)
    weaknesses = Column(Text, nullable=True)
    detailed_feedback = Column(Text, nullable=True)
    
    interview_outcome = Column(Enum(InterviewOutcome), nullable=False)
    improvement_recommendations = Column(JSON, nullable=True)  # AI generated actionable advice
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    match = relationship("MatchShortlist", back_populates="interviews")
    student = relationship("Student", back_populates="interviews")
    job = relationship("JobPosting", back_populates="interviews")
