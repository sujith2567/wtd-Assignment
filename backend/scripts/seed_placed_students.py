import sys
import os
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models.placed_student import PlacedStudent

def seed_placed_students():
    db = SessionLocal()
    try:
        count = db.query(PlacedStudent).count()
        if count > 0:
            print(f"[*] placed_students table already has {count} records. Skipping seed.")
            return

        samples = [
            {
                "student_name": "Aarav Mehta",
                "company_name": "Google",
                "role_title": "Software Engineer (Backend)",
                "cgpa": Decimal("9.45"),
                "domain": "Software Development",
                "talents": ["Python", "FastAPI", "Distributed Systems", "SQL", "Docker"],
                "placement_year": 2024,
                "raw_resume_text": "Experienced in building high-throughput REST APIs using FastAPI, microservices architecture, Docker containerization, PostgreSQL, and Python backend systems."
            },
            {
                "student_name": "Priya Ananth",
                "company_name": "Microsoft",
                "role_title": "AI / ML Engineer",
                "cgpa": Decimal("9.12"),
                "domain": "Machine Learning",
                "talents": ["PyTorch", "Scikit-Learn", "NLP", "TF-IDF", "Python"],
                "placement_year": 2024,
                "raw_resume_text": "Machine learning researcher focused on Natural Language Processing, text classification algorithms, Scikit-Learn TF-IDF vectorization, PyTorch neural networks, and model explainability."
            },
            {
                "student_name": "Rohan Deshmukh",
                "company_name": "Amazon",
                "role_title": "Frontend Developer",
                "cgpa": Decimal("8.75"),
                "domain": "Web Development",
                "talents": ["React", "JavaScript", "TypeScript", "CSS3", "Vite"],
                "placement_year": 2024,
                "raw_resume_text": "Frontend engineer specializing in React 19, responsive UI design, modern JavaScript ES6+, state management, single page applications, and CSS architecture."
            },
            {
                "student_name": "Sneha Reddy",
                "company_name": "Deloitte",
                "role_title": "Data Analyst",
                "cgpa": Decimal("8.60"),
                "domain": "Data Science & Analytics",
                "talents": ["SQL", "Pandas", "Power BI", "Data Visualization", "Python"],
                "placement_year": 2024,
                "raw_resume_text": "Data analytics consultant proficient in SQL database queries, Pandas data manipulation, Power BI executive dashboards, exploratory data analysis, and statistical modeling."
            },
            {
                "student_name": "Vikram Kulkarni",
                "company_name": "Cisco",
                "role_title": "DevOps & Cloud Engineer",
                "cgpa": Decimal("8.90"),
                "domain": "Cloud & Infrastructure",
                "talents": ["AWS", "Kubernetes", "Linux", "CI/CD", "Terraform"],
                "placement_year": 2024,
                "raw_resume_text": "Cloud infrastructure engineer with hands-on expertise in AWS cloud services, Kubernetes cluster deployment, Terraform infrastructure as code, and Linux sysadmin."
            }
        ]

        for s in samples:
            rec = PlacedStudent(**s)
            db.add(rec)
        db.commit()
        print(f"[*] Successfully seeded {len(samples)} sample placed student records!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_placed_students()
