import sys
import os
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import engine

def migrate():
    print("[*] Checking / Adding 'domain_label' column to students table...")
    with engine.connect() as conn:
        # Check if column exists
        res = conn.execute(text("SHOW COLUMNS FROM students LIKE 'domain_label';")).fetchall()
        if not res:
            conn.execute(text("ALTER TABLE students ADD COLUMN domain_label VARCHAR(100) NULL AFTER raw_resume_text;"))
            conn.commit()
            print(" -> Added 'domain_label' column to students table.")
        else:
            print(" -> 'domain_label' column already exists.")
            
        # If any students have NULL domain_label but have predicted_domain, copy it over as ground truth
        conn.execute(text("UPDATE students SET domain_label = predicted_domain WHERE domain_label IS NULL AND predicted_domain IS NOT NULL;"))
        conn.commit()
        print(" -> Synchronized domain labels.")

if __name__ == "__main__":
    migrate()
