import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models.readiness import ReadinessQuestion

def seed_questions():
    db = SessionLocal()
    
    # Check if already seeded
    existing_count = db.query(ReadinessQuestion).count()
    if existing_count > 0:
        print(f"[*] Readiness questions already seeded ({existing_count} records). Skipping.")
        db.close()
        return

    standard_options = [
        {"text": "Needs Significant Work (0-20%)", "points": 1},
        {"text": "Basic Concept Awareness (40%)", "points": 2},
        {"text": "Intermediate Competency (60%)", "points": 3},
        {"text": "Proficient & Practice Ready (80%)", "points": 4},
        {"text": "Advanced / Mastered (100%)", "points": 5},
    ]

    questions_data = [
        # --- Software Development ---
        {
            "domain": "Software Development",
            "question_text": "How comfortable are you solving Data Structures & Algorithms problems (Arrays, Linked Lists, Trees, Graphs)?",
            "category": "DSA",
            "weight": 2,
            "options_json": standard_options
        },
        {
            "domain": "Software Development",
            "question_text": "Can you accurately analyze the Time and Space Complexity (Big-O notation) of code snippets?",
            "category": "DSA",
            "weight": 1,
            "options_json": standard_options
        },
        {
            "domain": "Software Development",
            "question_text": "How strong are your Object-Oriented Programming (OOP) fundamentals (Inheritance, Polymorphism, Abstraction, Encapsulation)?",
            "category": "Core Tech",
            "weight": 2,
            "options_json": standard_options
        },
        {
            "domain": "Software Development",
            "question_text": "Rate your proficiency with SQL databases, schema normalization, and complex JOIN queries.",
            "category": "Core Tech",
            "weight": 1,
            "options_json": standard_options
        },
        {
            "domain": "Software Development",
            "question_text": "How confident are you explaining your past projects, architecture decisions, and code tradeoffs during a technical interview?",
            "category": "Communication",
            "weight": 1,
            "options_json": standard_options
        },
        {
            "domain": "Software Development",
            "question_text": "How consistent are you with quantitative aptitude, logical reasoning, and speed math practice tests?",
            "category": "Aptitude",
            "weight": 1,
            "options_json": standard_options
        },

        # --- Data Science & Analytics ---
        {
            "domain": "Data Science & Analytics",
            "question_text": "Rate your command of Python data libraries (Pandas, NumPy, Matplotlib, Seaborn) for ETL and exploratory data analysis.",
            "category": "Core Tech",
            "weight": 2,
            "options_json": standard_options
        },
        {
            "domain": "Data Science & Analytics",
            "question_text": "How well do you understand statistical concepts (Hypothesis testing, P-values, A/B testing, Bayes Theorem)?",
            "category": "Core Tech",
            "weight": 2,
            "options_json": standard_options
        },
        {
            "domain": "Data Science & Analytics",
            "question_text": "How proficient are you in writing SQL queries involving Window functions, Aggregations, and CTEs?",
            "category": "Core Tech",
            "weight": 1,
            "options_json": standard_options
        },
        {
            "domain": "Data Science & Analytics",
            "question_text": "How strong is your analytical aptitude for interpreting charts, trends, and business data problems?",
            "category": "Aptitude",
            "weight": 1,
            "options_json": standard_options
        },
        {
            "domain": "Data Science & Analytics",
            "question_text": "How clearly can you present data insights and executive summaries to non-technical stakeholders?",
            "category": "Communication",
            "weight": 1,
            "options_json": standard_options
        },

        # --- Web Development ---
        {
            "domain": "Web Development",
            "question_text": "How proficient are you in modern frontend frameworks (React, Vue, state management, hooks)?",
            "category": "Core Tech",
            "weight": 2,
            "options_json": standard_options
        },
        {
            "domain": "Web Development",
            "question_text": "Rate your mastery of RESTful API design, HTTP status codes, authentication (JWT/OAuth), and CORS.",
            "category": "Core Tech",
            "weight": 2,
            "options_json": standard_options
        },
        {
            "domain": "Web Development",
            "question_text": "How experienced are you with HTML5, CSS3, responsive layout design, and modern CSS frameworks?",
            "category": "Core Tech",
            "weight": 1,
            "options_json": standard_options
        },
        {
            "domain": "Web Development",
            "question_text": "How well can you solve logical DOM manipulation or JavaScript algorithm coding challenges?",
            "category": "DSA",
            "weight": 1,
            "options_json": standard_options
        },
        {
            "domain": "Web Development",
            "question_text": "How confident are you conducting live code walkthroughs and explaining web architecture choices?",
            "category": "Communication",
            "weight": 1,
            "options_json": standard_options
        },

        # --- Machine Learning ---
        {
            "domain": "Machine Learning",
            "question_text": "How well do you understand classical ML algorithms (Linear/Logistic Regression, Decision Trees, Random Forests, SVM, Clustering)?",
            "category": "Core Tech",
            "weight": 2,
            "options_json": standard_options
        },
        {
            "domain": "Machine Learning",
            "question_text": "Rate your experience using deep learning frameworks (PyTorch, TensorFlow, Keras) and neural networks.",
            "category": "Core Tech",
            "weight": 2,
            "options_json": standard_options
        },
        {
            "domain": "Machine Learning",
            "question_text": "How comfortable are you with Linear Algebra, Vector Calculus, and Optimization fundamentals behind ML?",
            "category": "Core Tech",
            "weight": 1,
            "options_json": standard_options
        },
        {
            "domain": "Machine Learning",
            "question_text": "How proficient are you in data preprocessing, feature engineering, and model evaluation metrics (ROC-AUC, Precision/Recall)?",
            "category": "Core Tech",
            "weight": 1,
            "options_json": standard_options
        },
        {
            "domain": "Machine Learning",
            "question_text": "How effectively can you explain model tradeoffs, bias-variance trade-offs, and feature importance to interviewers?",
            "category": "Communication",
            "weight": 1,
            "options_json": standard_options
        },
    ]

    print(f"[*] Seeding {len(questions_data)} domain readiness questions into database...")
    for q_dict in questions_data:
        q = ReadinessQuestion(**q_dict)
        db.add(q)
    
    db.commit()
    db.close()
    print(" -> Readiness questions successfully seeded!")

if __name__ == "__main__":
    seed_questions()
