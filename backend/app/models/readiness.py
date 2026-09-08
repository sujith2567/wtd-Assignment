from sqlalchemy import Column, Integer, String, Text, Float, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.app.core.database import Base

class ReadinessQuestion(Base):
    __tablename__ = "readiness_questions"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(100), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    category = Column(String(100), nullable=False) # e.g. DSA, Aptitude, Communication, System Design
    weight = Column(Integer, default=1)
    options_json = Column(JSON, nullable=False) # List of {"text": str, "points": int (0-5)}

class ReadinessSubmission(Base):
    __tablename__ = "readiness_submissions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    domain = Column(String(100), nullable=False)
    total_score_percent = Column(Float, nullable=False)
    strong_areas = Column(JSON, default=list) # List of category strings
    weak_areas = Column(JSON, default=list) # List of category strings
    category_scores_json = Column(JSON, default=dict) # {"DSA": 85.0, "Communication": 60.0}
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student")
