"""
migrate_add_fairness_columns.py
================================
Adds the `category` (reservation / community category) column to the students
table and backfills realistic Indian-campus category distribution using
deterministic SQL arithmetic so the assignment is reproducible across runs
without re-running Python over every row.

Distribution seeded on MOD(id, 200) ranges (sum = 200 slots → proportional):
  General  : MOD(id,200) IN [0..99]   → 50 %
  OBC      : MOD(id,200) IN [100..153] → 27 %
  SC       : MOD(id,200) IN [154..183] → 15 %
  ST       : MOD(id,200) IN [184..198] → 7.5 %
  EWS      : MOD(id,200) = 199         → 0.5 %

Safe to re-run: guards against column-already-exists and only touches
rows where category IS NULL.
"""

import sys
import os
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import engine


def migrate():
    print("\n[*] migrate_add_fairness_columns.py — starting...")

    with engine.connect() as conn:
        # ------------------------------------------------------------------ #
        # 1. Add `category` column (idempotent)                               #
        # ------------------------------------------------------------------ #
        res = conn.execute(
            text("SHOW COLUMNS FROM students LIKE 'category';")
        ).fetchall()

        if not res:
            conn.execute(text(
                "ALTER TABLE students "
                "ADD COLUMN category VARCHAR(50) NULL "
                "AFTER gender;"
            ))
            conn.commit()
            print("  -> Added 'category' column to students table.")
        else:
            print("  -> 'category' column already exists — skipping ALTER.")

        # ------------------------------------------------------------------ #
        # 2. Backfill NULL rows with weighted distribution                    #
        # ------------------------------------------------------------------ #
        null_count = conn.execute(
            text("SELECT COUNT(*) FROM students WHERE category IS NULL;")
        ).scalar()

        if null_count == 0:
            print("  -> No NULL category rows found — backfill not needed.")
        else:
            print(f"  -> Backfilling {null_count} student rows with category…")

            # Use a CASE on MOD(id, 200) for a deterministic distribution.
            conn.execute(text("""
                UPDATE students
                SET category = CASE
                    WHEN MOD(id, 200) < 100 THEN 'General'
                    WHEN MOD(id, 200) < 154 THEN 'OBC'
                    WHEN MOD(id, 200) < 184 THEN 'SC'
                    WHEN MOD(id, 200) < 199 THEN 'ST'
                    ELSE 'EWS'
                END
                WHERE category IS NULL;
            """))
            conn.commit()
            print(f"  -> Backfilled {null_count} rows.")

        # ------------------------------------------------------------------ #
        # 3. Verify distribution                                               #
        # ------------------------------------------------------------------ #
        rows = conn.execute(
            text("SELECT category, COUNT(*) AS cnt FROM students GROUP BY category ORDER BY cnt DESC;")
        ).fetchall()
        print("\n  Category distribution after migration:")
        total = sum(r[1] for r in rows)
        for row in rows:
            pct = row[1] / total * 100 if total else 0
            print(f"    {row[0] or 'NULL':12s}  {row[1]:4d}  ({pct:.1f}%)")

    print("\n[OK] Migration complete.\n")


if __name__ == "__main__":
    migrate()
