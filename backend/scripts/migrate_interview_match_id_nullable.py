import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from backend.app.core.database import engine

def migrate():
    print("Modifying match_id column in interview_records table to allow NULL...")
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE interview_records MODIFY match_id INT NULL;"))
        conn.commit()
    print("Migration successful! match_id is now nullable.")

if __name__ == "__main__":
    migrate()
