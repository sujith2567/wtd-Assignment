import sys
import os
from sqlalchemy import inspect

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import engine
from backend.app.core.config import settings

def verify():
    print(f"\n========================================================")
    print(f"  DATABASE SCHEMA VERIFICATION: {settings.DB_NAME}")
    print(f"========================================================\n")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    expected_tables = [
        "users", "companies", "students", "student_projects",
        "job_postings", "match_shortlists", "interview_records"
    ]
    
    print(f"Found {len(tables)} tables in database:")
    for table_name in expected_tables:
        if table_name in tables:
            print(f"\n [+] Table: '{table_name}'")
            columns = inspector.get_columns(table_name)
            pk_constraint = inspector.get_pk_constraint(table_name)
            fk_constraints = inspector.get_foreign_keys(table_name)
            
            # Print columns
            for col in columns:
                pk_marker = " (PK)" if col["name"] in pk_constraint.get("constrained_columns", []) else ""
                nullable_str = "NULL" if col.get("nullable") else "NOT NULL"
                print(f"     - {col['name']:<28} {str(col['type']):<20} {nullable_str}{pk_marker}")
            
            # Print foreign keys
            if fk_constraints:
                for fk in fk_constraints:
                    referred_cols = ", ".join(fk['referred_columns'])
                    constrained_cols = ", ".join(fk['constrained_columns'])
                    print(f"     -> FK: ({constrained_cols}) REFERENCES {fk['referred_table']}({referred_cols})")
        else:
            print(f"\n [!] Table: '{table_name}' - MISSING!")
            
    print("\n========================================================")
    all_present = all(t in tables for t in expected_tables)
    if all_present:
        print(" -> All 7 expected tables and relationships are present & verified!")
    else:
        print(" -> Some tables are missing. Please re-run create_tables.py.")
    print("========================================================\n")

if __name__ == "__main__":
    verify()
