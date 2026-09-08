from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import LONGTEXT

from datetime import datetime
from backend.app.core.database import Base

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    roll_number = Column(String(50), unique=True, index=True, nullable=False)
    department = Column(String(100), nullable=False)
    batch_year = Column(Integer, nullable=False)
    cgpa = Column(Numeric(precision=3, scale=2), nullable=False)
    active_backlogs = Column(Integer, default=0, nullable=False)
    history_backlogs = Column(Integer, default=0, nullable=False)
    phone = Column(String(20), nullable=True)
    gender = Column(String(20), nullable=True)
    category = Column(String(50), nullable=True)  # Reservation/community category: General, OBC, SC, ST, EWS
    skills = Column(JSON, nullable=True)  # List of skill strings: ["Python", "FastAPI", "React"]
    raw_resume_text = Column(LONGTEXT, nullable=True)  # Extracted text from uploaded resume
    domain_label = Column(String(100), nullable=True)  # Ground-truth target domain label
    predicted_domain = Column(String(100), nullable=True)  # AI multi-class prediction
    domain_confidence = Column(Float, nullable=True)  # Confidence score 0.0 - 1.0
    section_id = Column(Integer, ForeignKey("sections.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="student_profile")
    section = relationship("Section", back_populates="students")
    projects = relationship("StudentProject", back_populates="student", cascade="all, delete-orphan")
    matches = relationship("MatchShortlist", back_populates="student", cascade="all, delete-orphan")
    interviews = relationship("InterviewRecord", back_populates="student", cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        return self.user.full_name if self.user else ""


class StudentProject(Base):
    __tablename__ = "student_projects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    tech_stack = Column(JSON, nullable=True)  # List of technologies: ["Python", "PyTorch"]
    github_url = Column(String(255), nullable=True)
    live_url = Column(String(255), nullable=True)
    domain_tag = Column(String(100), nullable=True)  # e.g., 'Machine Learning', 'Fullstack Web'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    student = relationship("Student", back_populates="projects")
