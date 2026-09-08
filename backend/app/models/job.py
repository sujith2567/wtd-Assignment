from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Float, Enum, JSON
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from backend.app.core.database import Base

class JobStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"

class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    target_domain = Column(String(100), nullable=False)
    description = Column(LONGTEXT, nullable=False)
    min_cgpa = Column(Numeric(precision=3, scale=2), default=6.00, nullable=False)
    max_backlogs_allowed = Column(Integer, default=0, nullable=False)
    required_skills = Column(JSON, nullable=False)   # List of strings: ["Python", "SQL"]
    preferred_skills = Column(JSON, nullable=True)   # List of strings: ["Docker", "AWS"]
    salary_range = Column(String(100), nullable=True)  # e.g., '6 - 10 LPA'
    location = Column(String(100), nullable=True)
    status = Column(Enum(JobStatus), default=JobStatus.ACTIVE, nullable=False)
    buffer_threshold_percent = Column(Float, default=10.0, nullable=False)  # e.g., allow 10% CGPA delta if strong portfolio
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    company = relationship("Company", back_populates="job_postings")
    matches = relationship("MatchShortlist", back_populates="job", cascade="all, delete-orphan")
    interviews = relationship("InterviewRecord", back_populates="job", cascade="all, delete-orphan")

    @property
    def company_name(self) -> str:
        return self.company.company_name if self.company else ""

