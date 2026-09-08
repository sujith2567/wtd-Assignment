"""
Phase 7 Migration: Add sections table and section_id FK to students.

Run this script from the project root:
    python backend/scripts/migrate_add_sections.py

Compatible with MySQL 5.7+ and MySQL 8.0+.
Uses try/except guards rather than IF NOT EXISTS on ALTER TABLE
(MySQL 5.7 does not support ADD COLUMN IF NOT EXISTS).
"""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from backend.app.core.database import engine


def run_migration():
    with engine.connect() as conn:
        # ----------------------------------------------------------------
        # 1. Create sections table
        # ----------------------------------------------------------------
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sections (
                id          INT          NOT NULL AUTO_INCREMENT,
                name        VARCHAR(100) NOT NULL,
                created_by  INT          NULL,
                created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uq_sections_name (name),
                KEY        ix_sections_id   (id),
                CONSTRAINT fk_sections_created_by
                    FOREIGN KEY (created_by) REFERENCES users (id)
                    ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """))
        print("[OK] sections table created (or already exists).")

        # ----------------------------------------------------------------
        # 2. Add section_id FK column to students (MySQL 5.7-safe)
        # ----------------------------------------------------------------
        # Check if column already exists before adding it
        result = conn.execute(text("""
            SELECT COUNT(*) AS cnt
            FROM   information_schema.COLUMNS
            WHERE  TABLE_SCHEMA = DATABASE()
            AND    TABLE_NAME   = 'students'
            AND    COLUMN_NAME  = 'section_id';
        """))
        row = result.fetchone()
        if row[0] == 0:
            conn.execute(text("""
                ALTER TABLE students
                ADD COLUMN section_id INT NULL,
                ADD KEY ix_students_section_id (section_id),
                ADD CONSTRAINT fk_students_section_id
                    FOREIGN KEY (section_id) REFERENCES sections (id)
                    ON DELETE SET NULL;
            """))
            print("[OK] section_id column and FK added to students table.")
        else:
            print("[SKIP] section_id column already exists on students table.")

        conn.commit()

    print("\nPhase 7 migration complete.")


if __name__ == "__main__":
    run_migration()
