from sqlalchemy import Column, Integer, String, Numeric, DateTime, JSON, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from datetime import datetime
from backend.app.core.database import Base

class PlacedStudent(Base):
    __tablename__ = "placed_students"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_name = Column(String(150), nullable=False)
    company_name = Column(String(150), nullable=False)
    role_title = Column(String(150), nullable=False)
    cgpa = Column(Numeric(precision=3, scale=2), nullable=False)
    domain = Column(String(100), nullable=False)
    talents = Column(JSON, nullable=True)  # e.g., ["Python", "System Design", "AWS"]
    placement_year = Column(Integer, default=2024, nullable=False)
    outcome = Column(String(50), default="PLACED", nullable=False)
    raw_resume_text = Column(LONGTEXT, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
