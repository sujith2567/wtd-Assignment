from sqlalchemy import Column, Integer, DateTime, ForeignKey, Float, Boolean, Enum, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from backend.app.core.database import Base

class MatchTier(str, enum.Enum):
    STRICT_MATCH = "strict_match"
    BUFFER_MATCH = "buffer_match"
    UNQUALIFIED = "unqualified"

class RecruiterStatus(str, enum.Enum):
    SUGGESTED = "suggested"
    SHORTLISTED = "shortlisted"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    REJECTED = "rejected"
    OFFERED = "offered"

class MatchShortlist(Base):
    __tablename__ = "match_shortlists"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Matching Scores & Explainability
    overall_score = Column(Float, nullable=False)  # Weighted composite (0.0 - 1.0)
    semantic_similarity = Column(Float, nullable=False)  # Cosine similarity on embeddings
    skill_match_score = Column(Float, nullable=False)    # Ratio of required/preferred skills matched
    academic_score = Column(Float, nullable=False)       # Normalized academic score
    
    match_tier = Column(Enum(MatchTier), nullable=False)  # strict vs buffer
    explainability_summary = Column(JSON, nullable=True) # AI rationale payload
    
    # Workflow Tracking
    recruiter_status = Column(Enum(RecruiterStatus), default=RecruiterStatus.SUGGESTED, nullable=False)
    admin_dispatched = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Constraints
    __table_args__ = (
        UniqueConstraint("job_id", "student_id", name="uq_job_student_match"),
    )

    # Relationships
    job = relationship("JobPosting", back_populates="matches")
    student = relationship("Student", back_populates="matches")
    interviews = relationship("InterviewRecord", back_populates="match", cascade="all, delete-orphan")
