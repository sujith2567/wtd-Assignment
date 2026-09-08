# PlaceMatch AI — Automated Campus Placement Pipeline

**PlaceMatch AI** is an AI-powered automated campus recruitment and talent matching platform developed for 3rd-year engineering placement management. It replaces legacy hard-filtering spreadsheets with a two-tiered adaptive matching architecture powered by multi-class machine learning domain classification and transparent feature attribution.

---

## Key Features & Highlights

1. **Multi-Role Portal**: Dedicated, role-protected dashboards for **College Administrators**, **Recruiters / Companies**, and **Students**.
2. **AI Domain Classification & Explainability**: Concatenates resume text, skill inventories, and project descriptions to classify students into engineering domains using TF-IDF vectorization ($1, 2$ n-grams) and regularized Multinomial Logistic Regression ($87.25\%$ 5-fold CV accuracy). Provides transparent feature attribution and human-readable summaries explaining the model's rationale.
3. **Adaptive Buffer Matching (Core Novelty)**: Replaces binary CGPA cutoffs with a two-tiered candidate promotion pipeline:
   - **Strict Match**: Candidates meeting hard CGPA and backlog criteria.
   - **Adaptive Buffer Match (AI Promoted)**: Rescues near-miss candidates who fall within a configurable CGPA delta ($\le 10\%$) or backlog margin ($+1$), provided their AI domain-fit confidence clears a strict threshold ($\ge 70\%$).
4. **Lightweight Interview Feedback Module**: Enables recruiters to log structured 1–10 scores (Technical, Communication, Problem Solving), decision outcomes (`PASSED`, `FAILED`, `ON_HOLD`), and auto-filled template feedback suggestions, with multi-role visibility for students and college admins.
5. **Anti-Leakage Synthetic Data Pipeline**: Includes a 400-student, 40-job synthetic data generator v2 with shared cross-domain skill pools and ~18% noisy labels.

---

## Tech Stack

- **Frontend**: React 19, Vite, React Router v7, Plain CSS (Inter font system).
- **Backend**: FastAPI (Python 3.11), SQLAlchemy ORM, Pydantic v2, PyMySQL.
- **Machine Learning**: Scikit-Learn (TF-IDF Vectorizer + Multinomial Logistic Regression), Joblib, NumPy, Pandas.
- **Database**: MySQL Server.

---

## Project Structure

```text
placematch/
├── backend/
│   ├── app/
│   │   ├── api/v1/         # API Routers (auth, students, jobs, matching, interviews)
│   │   ├── core/           # Database setup, Security (JWT/bcrypt), Config
│   │   ├── models/         # SQLAlchemy ORM models (User, Student, Job, Match, Interview)
│   │   ├── schemas/        # Pydantic validation schemas
│   │   └── services/       # ML Domain Classifier Service & Logic
│   └── scripts/            # Training, Synthetic Data, Migrations, Verification Suites
├── frontend/
│   ├── src/
│   │   ├── admin.jsx       # Admin Dashboard components & views
│   │   ├── recruiter.jsx   # Recruiter Dashboard & Shortlist Modal
│   │   ├── student.jsx     # Student Profile, Explanation & Recommendations
│   │   ├── api.jsx         # HTTP Client & Auth Provider
│   │   └── App.jsx         # App routing & role-based route guards
├── README.md
└── .gitignore
```

---

## Setup & Running Locally

### Prerequisites
- **Python 3.11+** installed.
- **Node.js 18+** & `npm` installed.
- **MySQL Database Server** running locally.

---

### 1. Database & Backend Setup

1. **Configure Environment Variables**:
   Create a `.env` file in the root directory (or copy from `.env.example`):
   ```env
   DATABASE_URL=mysql+pymysql://root:password@localhost:3306/placematch_db
   SECRET_KEY=your_jwt_secret_key_here
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=1440
   ```

2. **Set Up Python Virtual Environment**:
   ```bash
   # From project root
   python -m venv venv
   
   # Activate virtual environment
   # Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # Linux/macOS:
   source venv/bin/activate
   
   # Install backend dependencies
   pip install -r requirements.txt
   ```

3. **Initialize Database Tables & Synthetic Dataset**:
   ```bash
   # Create MySQL database schema tables
   python backend/scripts/create_tables.py

   # Generate anti-leakage synthetic dataset (400 students, 40 jobs)
   python backend/scripts/generate_synthetic_data.py

   # Train the domain classifier model
   python backend/scripts/train_domain_classifier.py
   ```

4. **Start the FastAPI Backend Server**:
   ```bash
   uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   The backend API documentation is accessible at `http://127.0.0.1:8000/docs`.

---

### 2. Frontend Setup

1. **Install Frontend Dependencies**:
   ```bash
   cd frontend
   npm install
   ```

2. **Configure Environment Variable**:
   Create `frontend/.env`:
   ```env
   VITE_API_URL=http://127.0.0.1:8000
   ```

3. **Start Development Server**:
   ```bash
   npm run dev
   ```
   The frontend application will be running at `http://localhost:5173`.

4. **Build Production Bundle**:
   ```bash
   npm run build
   ```

---

## Demo Credentials (Pre-seeded Demo Accounts)

| Role | Email | Password | Description |
| :--- | :--- | :--- | :--- |
| **College Administrator** | `admin@placematch.edu` | `password123` | College Placement Director |
| **Recruiter / Company** | `recruiter@google.com` | `password123` | Tech Recruiter (Google) |
| **Student** | `student@placematch.edu` | `password123` | Candidate (Alex Sharma) |

---

## Key API Endpoints

### Authentication & Users
- `POST /api/v1/auth/register` — Account registration (Student, Recruiter, Admin).
- `POST /api/v1/auth/login` — Sign in and obtain OAuth2 JWT bearer token.
- `GET /api/v1/auth/me` — Return current authenticated user profile.

### Students
- `GET /api/v1/students/profile` — Fetch logged-in student's record (`full_name`, CGPA, backlogs, skills, resume text).
- `GET /api/v1/students/` — List all registered students (searchable by name/roll #, filterable by domain).

### Jobs & Recruitment
- `POST /api/v1/jobs/` — Create new job posting (`min_cgpa`, `max_backlogs_allowed`, `target_domain`, `buffer_threshold_percent`).
- `GET /api/v1/jobs/my-jobs` — Fetch job postings for logged-in recruiter's company.
- `GET /api/v1/jobs/` — List all active job postings across companies.

### Matching & Explainability
- `GET /api/v1/matching/jobs/{job_id}/baseline-candidates` — Rank candidates with strict & buffer match tiers (`include_buffer=true`).
- `GET /api/v1/matching/student/{student_id}/explanation` — Read-only explainability breakdown (probability distribution, contributing factors, human summary).

### Interview Feedback Module
- `POST /api/v1/interviews/` — Log interview feedback (scores, outcome, notes).
- `POST /api/v1/interviews/template-suggestions` — Compute dynamic template feedback suggestions.
- `GET /api/v1/interviews/my-interviews` — Student personal interview outcome history.
- `GET /api/v1/interviews/` — Campus-wide placement interview records (Admin & Recruiter).
