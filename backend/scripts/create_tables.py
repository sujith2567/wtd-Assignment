import sys
import os

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import engine, Base
from backend.app.models import (
    User, Company, Student, StudentProject, JobPosting, MatchShortlist, InterviewRecord, PlacedStudent, ReadinessQuestion, ReadinessSubmission, Application
)

def create_all_tables():
    print("[*] Creating all database tables in MySQL using SQLAlchemy metadata...")
    try:
        Base.metadata.create_all(bind=engine)
        print(" -> All tables created successfully in MySQL!")
        return True
    except Exception as e:
        print(f"[!] Error creating tables: {e}")
        return False

if __name__ == "__main__":
    success = create_all_tables()
    if not success:
        sys.exit(1)
