"""
Synthetic data generator for PlaceMatch.

v2 (post Step 5): Re-designed to break the prior generator-vs-label leakage
that produced a perfect confusion matrix. Concretely:

1. Skills are no longer siloed per domain. Each domain pool keeps a small
   set of *signature* skills (the strong discriminators) and a large shared
   pool of *cross-domain* skills (Python, SQL, Git, Docker, Linux, ...).
   Real students mix signature + shared + neighbor-domain skills.
2. ~18% of students are deliberately assigned a "noisy" domain label
   (mismatched with their dominant skill/project signal) to mirror
   real-world placement outcomes that don't perfectly track resumes.
3. Generic soft-skill phrases (teamwork, communication, problem-solving,
   agile, etc.) are added to a non-trivial fraction of resumes regardless
   of domain, so they cannot be used as discriminators.
4. Resume verbosity is sampled from a style distribution (terse /
   standard / verbose) instead of one fixed template per domain.
5. The chosen set of skills and projects is also perturbed by random
   substitution: a student may have 1-2 neighbor-domain skills and at
   least one soft skill, and a noisy-label student has their primary
   project's domain_tag intentionally drifted away from domain_label.

The script is idempotent on Users/Companies/JobPostings (skip-if-exists)
and *destructive* on Students / StudentProjects (wipe + regenerate) when
called with the --regenerate-students flag (default). It also re-creates
job postings if --regenerate-jobs is passed.
"""

import sys
import os
import random
import argparse
from faker import Faker
from datetime import datetime
from decimal import Decimal

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.core.database import SessionLocal
from backend.app.models import (
    User, UserRole, Company, Student, StudentProject, JobPosting, JobStatus
)
import bcrypt

# --------------------------------------------------------------------------
# Reproducibility: seeded once per run for deterministic CV behavior
# --------------------------------------------------------------------------
def seed_random(seed: int = 2025) -> None:
    random.seed(seed)
    fake.seed_instance(seed)

fake = Faker("en_IN")

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


# ==========================================================================
# Domain taxonomy (kept identical to Step 5 to preserve label compatibility)
# ==========================================================================
DOMAINS = [
    "Software Development",
    "Data Science / AI",
    "Quality Assurance & Testing",
    "DevOps & Cloud Engineering",
    "Technical Support & Cybersecurity",
]

# Reservation / community category — follows a plausible Indian campus split.
CATEGORIES = ["General", "OBC", "SC", "ST", "EWS"]
CATEGORY_WEIGHTS = [50, 27, 15, 7, 1]  # relative weights (sum = 100)

# Signature skills: the *strong* discriminators per domain. These are
# intentionally a small set so the classifier must rely on combinations.
SIGNATURE_SKILLS = {
    "Software Development": [
        "React", "Next.js", "Django", "FastAPI", "Spring Boot", "GraphQL",
        "Microservices", "REST APIs", "TypeScript", "Node.js", "Redux",
    ],
    "Data Science / AI": [
        "PyTorch", "TensorFlow", "Hugging Face", "LangChain", "RAG",
        "Computer Vision", "NLP", "XGBoost", "SHAP", "Pandas", "Seaborn",
    ],
    "Quality Assurance & Testing": [
        "Selenium", "Cypress", "Playwright", "JMeter", "TestNG",
        "Allure Reports", "Page Object Model", "Test Rail", "Appium",
        "Regression Testing", "API Testing",
    ],
    "DevOps & Cloud Engineering": [
        "Kubernetes", "Terraform", "Helm", "Ansible", "Prometheus",
        "Grafana", "GitHub Actions", "Jenkins", "AWS Lambda", "Kinesis",
        "OpenSearch", "Site Reliability",
    ],
    "Technical Support & Cybersecurity": [
        "Wireshark", "Nessus", "Snort IDS", "Active Directory", "GPO",
        "SIEM", "Splunk", "OpenVAS", "VPN", "Firewalls", "ITIL",
        "Packet Analysis", "CVE Remediation",
    ],
}

# Cross-domain skills: appear in 2+ pools to create real overlap.
# The classifier can no longer treat "Python appeared => Software Dev".
CROSS_DOMAIN_SKILLS = {
    "Python":           {"Software Development", "Data Science / AI",
                          "Quality Assurance & Testing", "DevOps & Cloud Engineering",
                          "Technical Support & Cybersecurity"},
    "SQL":              {"Software Development", "Data Science / AI",
                          "Quality Assurance & Testing", "DevOps & Cloud Engineering"},
    "Git":              {"Software Development", "Quality Assurance & Testing",
                          "DevOps & Cloud Engineering", "Technical Support & Cybersecurity"},
    "Linux":            {"DevOps & Cloud Engineering", "Technical Support & Cybersecurity",
                          "Quality Assurance & Testing", "Data Science / AI"},
    "Docker":           {"Software Development", "DevOps & Cloud Engineering",
                          "Data Science / AI"},
    "Bash Scripting":   {"DevOps & Cloud Engineering", "Technical Support & Cybersecurity",
                          "Software Development"},
    "FastAPI":          {"Software Development", "Data Science / AI"},
    "CI/CD":            {"DevOps & Cloud Engineering", "Software Development",
                          "Quality Assurance & Testing"},
    "Java":             {"Software Development", "Quality Assurance & Testing"},
    "PostgreSQL":       {"Software Development", "Data Science / AI",
                          "DevOps & Cloud Engineering"},
    "Networking":       {"DevOps & Cloud Engineering", "Technical Support & Cybersecurity"},
    "AWS":              {"DevOps & Cloud Engineering", "Data Science / AI",
                          "Technical Support & Cybersecurity"},
    "Statistics":       {"Data Science / AI", "Quality Assurance & Testing"},
    "JIRA":             {"Quality Assurance & Testing", "Software Development",
                          "DevOps & Cloud Engineering"},
    "Communication":    set(DOMAINS),  # Soft skill, universal
    "Problem Solving":  set(DOMAINS),  # Soft skill, universal
    "Teamwork":         set(DOMAINS),  # Soft skill, universal
    "Agile Methodology": set(DOMAINS),
    "Time Management":  set(DOMAINS),
    "Presentation Skills": set(DOMAINS),
}

# Pool used at sampling time: each domain's "eligible skills" = its
# signatures + the cross-domain skills that include this domain. This
# makes any single skill non-discriminative; combinations become signal.
def eligible_skills_for(domain: str) -> list[str]:
    pool = list(SIGNATURE_SKILLS[domain])
    for skill, domains in CROSS_DOMAIN_SKILLS.items():
        if domain in domains:
            pool.append(skill)
    return pool


# Project templates: still varied by domain, but no longer deterministic
# 1:1 with the label — we will sometimes swap a project's domain_tag.
PROJECT_TEMPLATES = {
    "Software Development": [
        ("Fullstack E-Commerce Platform",
         "Built a scalable microservices-based shop with product catalog, cart, Stripe payments and JWT auth.",
         ["React", "FastAPI", "PostgreSQL", "Docker", "Redis"]),
        ("Real-time Collaborative Whiteboard",
         "Developed a low-latency multi-user canvas using WebSockets and React canvas API.",
         ["React", "Node.js", "WebSocket", "TailwindCSS"]),
        ("Task Management & Kanban System",
         "Designed a drag-and-drop workspace with team workspaces, notifications, and analytics.",
         ["TypeScript", "Next.js", "Django", "PostgreSQL"]),
        ("Social Media Content Aggregator",
         "Engineered a REST API backend scraping and aggregating developer blogs with caching.",
         ["Python", "FastAPI", "Redis", "MongoDB"]),
    ],
    "Data Science / AI": [
        ("Skin Lesion Classification using CNNs",
         "Trained ResNet-50 on HAM10000 medical imaging dataset achieving 92.4% accuracy.",
         ["Python", "PyTorch", "OpenCV", "Scikit-Learn"]),
        ("Autonomous Customer Churn Predictor",
         "Built an end-to-end ML pipeline with XGBoost, SHAP explainability, and Streamlit dashboard.",
         ["Python", "Scikit-Learn", "Pandas", "SHAP", "Streamlit"]),
        ("AI Conversational Q&A on Documents",
         "RAG pipeline leveraging LangChain, ChromaDB embeddings, and Mistral LLM.",
         ["Python", "LangChain", "Hugging Face", "FastAPI"]),
        ("Real-Time Traffic Anomaly Detector",
         "YOLOv8 vision model tracking vehicle congestion and license plates.",
         ["Python", "TensorFlow", "OpenCV", "Flask"]),
    ],
    "Quality Assurance & Testing": [
        ("E-Banking Test Automation Suite",
         "Automated 200+ regression and sanity test cases with Page Object Model architecture.",
         ["Selenium", "PyTest", "Python", "Allure Reports"]),
        ("REST API Performance & Load Testing Suite",
         "Benchmarked microservice endpoints under 5000 concurrent user load.",
         ["JMeter", "Postman", "Python", "Docker"]),
        ("Cross-Browser Mobile Testing Framework",
         "Appium automated test framework testing Android and iOS checkout workflows.",
         ["Appium", "TestNG", "Java", "GitLab CI"]),
        ("Continuous QA Pipeline with Cypress",
         "Integrated automated end-to-end UI testing into GitHub Actions pipeline.",
         ["Cypress", "JavaScript", "GitHub Actions", "JIRA"]),
    ],
    "DevOps & Cloud Engineering": [
        ("Multi-Region Kubernetes Cluster Deployment",
         "Provisioned HA Kubernetes cluster on AWS using Terraform and Helm charts.",
         ["AWS", "Kubernetes", "Terraform", "Helm"]),
        ("Automated Zero-Downtime CI/CD Pipeline",
         "Configured blue-green deployment pipeline with automated rollback triggers.",
         ["GitHub Actions", "Docker", "Jenkins", "Prometheus"]),
        ("Serverless Log Ingestion & Analytics",
         "Built AWS Lambda and Kinesis pipeline streaming infrastructure logs into OpenSearch.",
         ["AWS", "Python", "Docker", "Grafana"]),
        ("Infrastructure-as-Code Compliance Monitor",
         "Wrote custom Ansible playbooks auditing server security baselines.",
         ["Ansible", "Linux", "Bash", "Terraform"]),
    ],
    "Technical Support & Cybersecurity": [
        ("Intrusion Detection & Traffic Analyzer",
         "Deployed Snort IDS and automated PCAP packet parsing to detect port scans.",
         ["Wireshark", "Linux", "Python", "Bash"]),
        ("Enterprise Identity & Access Management Lab",
         "Configured Windows Server Active Directory with RBAC, GPO policies and SSO.",
         ["Active Directory", "Windows Server", "PowerShell", "LDAP"]),
        ("Vulnerability Assessment & Patch Pipeline",
         "Scanned university subnet using Nessus and OpenVAS, cataloging CVE remediations.",
         ["Nessus", "Linux", "Networking", "Python"]),
        ("Internal IT Helpdesk Ticketing System",
         "Implemented SLA-driven request tracking with automated diagnostic scripts.",
         ["Python", "MySQL", "Linux", "Bash"]),
    ],
}

# Neighbor-domain swap targets for "noisy" students. We pick a *near*
# domain to make the label non-trivially wrong but still defensible —
# a QA-labeled student might have a couple of SWE projects, not a
# cybersecurity-labeled student with no signal at all.
NEIGHBOR_DOMAINS = {
    "Software Development":               ["Data Science / AI", "Quality Assurance & Testing"],
    "Data Science / AI":                  ["Software Development", "Technical Support & Cybersecurity"],
    "Quality Assurance & Testing":        ["Software Development", "DevOps & Cloud Engineering"],
    "DevOps & Cloud Engineering":         ["Quality Assurance & Testing", "Technical Support & Cybersecurity"],
    "Technical Support & Cybersecurity":  ["DevOps & Cloud Engineering", "Data Science / AI"],
}

DEPARTMENTS = [
    "Computer Science & Engineering",
    "Information Technology",
    "Electronics & Communication Engineering",
    "Artificial Intelligence & Data Science",
]

COMPANY_DATA = [
    ("Google", "Technology / Cloud", "https://google.com", "careers@google.com", "Bengaluru"),
    ("Microsoft", "Technology / Software", "https://microsoft.com", "careers@microsoft.com", "Hyderabad"),
    ("Amazon", "E-Commerce / Cloud", "https://amazon.jobs", "hiring@amazon.jobs", "Bengaluru"),
    ("Zomato", "FoodTech", "https://zomato.com", "tech-hiring@zomato.com", "Gurugram"),
    ("Razorpay", "Fintech", "https://razorpay.com", "jobs@razorpay.com", "Bengaluru"),
    ("Infosys", "IT Services", "https://infosys.com", "campus@infosys.com", "Pune"),
    ("TCS", "IT Services", "https://tcs.com", "careers@tcs.com", "Mumbai"),
    ("Cisco", "Networking & Security", "https://cisco.com", "talent@cisco.com", "Bengaluru"),
    ("Accenture", "Consulting & Tech", "https://accenture.com", "recruitment@accenture.com", "Noida"),
    ("Swiggy", "Consumer Tech", "https://swiggy.com", "campus@swiggy.com", "Bengaluru"),
]

# Probability of generating a "noisy" student whose label is shifted
# from their dominant resume signal. Set in line with the report's
# expected realism band (~15-20%).
NOISY_LABEL_PROBABILITY = 0.18
# Probability of injecting generic soft-skill text into a resume.
SOFT_SKILL_TEXT_PROBABILITY = 0.70
# Probability of injecting a non-trivial generic-soft-skill block.
GENERIC_BLOCK_PROBABILITY = 0.45

SOFT_SKILL_PHRASES = [
    "Strong communication and presentation skills.",
    "Team player with proven collaboration across cross-functional teams.",
    "Demonstrated ability to learn quickly and adapt to new technologies.",
    "Excellent time management and organizational skills.",
    "Experience working in Agile Methodology environments.",
    "Committed to writing clean, maintainable, well-documented code.",
    "Strong problem-solving and analytical thinking abilities.",
    "Effective communicator with peers, mentors, and stakeholders.",
    "Active participant in hackathons, coding clubs, and tech communities.",
    "Passionate about continuous learning and professional development.",
]

# Resume verbosity styles. Each tuple: (header_lines, summary_lines).
RESUME_STYLES = {
    "terse":  ([],                                 ["Short summary."]),
    "standard": (["Domain Focus: {domain}"],       [2, 3]),  # 2-3 lines
    "verbose": ([
        "Domain Focus: {domain}",
        "Academic: CGPA {cgpa}, Department of {dept}",
        "Technical Proficiencies: {skills}",
    ], [4, 5]),
}


def pick_resume_style() -> str:
    """Sample a verbosity style with realistic weights."""
    return random.choices(
        ["terse", "standard", "verbose"],
        weights=[0.20, 0.55, 0.25],
        k=1,
    )[0]


def build_resume_text(name: str, domain: str, dept: str, cgpa: float,
                      chosen_skills: list[str], style: str,
                      include_soft_block: bool) -> str:
    """Generate a resume with varied verbosity, optional soft-skill block,
    and a domain-stated header that matches the *label* (so the label
    remains a defensible ground truth even when the skills below it
    are mismatched). The header is allowed to drift for noisy students
    by virtue of using `domain` (the label)."""
    header_lines, summary_range = RESUME_STYLES[style]
    skills_str = ", ".join(chosen_skills)

    header = "\n".join(line.format(
        domain=domain, cgpa=cgpa, dept=dept, skills=skills_str
    ) for line in header_lines)

    if isinstance(summary_range[0], int):
        n_lines = random.randint(summary_range[0], summary_range[1])
    else:
        n_lines = len(summary_range)

    summary_pool = [
        f"Dedicated engineering undergraduate with practical experience in {domain.lower()} technologies.",
        f"Hands-on academic and self-initiated projects in the {domain.lower()} space.",
        f"Seeking a full-time role where I can apply my {domain.lower()} skills to real-world products.",
        f"Quick learner with a strong foundation in computer-science fundamentals.",
        f"Looking to contribute to a team that values ownership, learning, and impact.",
        f"Comfortable owning features end-to-end, from design through deployment.",
    ]
    summary = " ".join(random.sample(summary_pool, min(n_lines, len(summary_pool))))

    soft_block = ""
    if include_soft_block:
        # 1-3 soft-skill sentences, generic across all domains
        n_soft = random.randint(1, 3)
        soft_block = " ".join(random.sample(SOFT_SKILL_PHRASES, n_soft))

    return f"Candidate: {name}\n{header}\nSummary: {summary}\n{soft_block}".strip()


def build_projects(student_name: str, dominant_skill_domain: str,
                   label_domain: str, num_projects: int,
                   noisy: bool) -> list[dict]:
    """Choose projects. For noisy students, deliberately draw 1-2
    projects from a *neighbor* domain so the project domain_tag is
    mismatched with the student label — that is the source of label
    noise the classifier must learn to handle."""
    # Pick the project-source domain(s).
    if noisy and random.random() < 0.7:
        # 70% of noisy students get at least one project from a neighbor.
        source_domains = [dominant_skill_domain] + random.sample(
            NEIGHBOR_DOMAINS[dominant_skill_domain],
            k=min(1, len(NEIGHBOR_DOMAINS[dominant_skill_domain])),
        )
    else:
        source_domains = [dominant_skill_domain]

    out = []
    for i in range(num_projects):
        src = random.choice(source_domains)
        title, desc, tech = random.choice(PROJECT_TEMPLATES[src])
        # Perturb tech stack: drop 1 tech 25% of the time, add a
        # neighbor-domain skill 25% of the time. Creates token overlap
        # in projects across domains.
        tech = list(tech)
        if random.random() < 0.25 and len(tech) > 2:
            tech.pop(random.randrange(len(tech)))
        if random.random() < 0.25:
            # Inject one cross-domain skill
            cross_pick = random.choice([
                "Python", "Docker", "Git", "Linux", "SQL", "AWS",
                "JIRA", "PostgreSQL", "Bash Scripting",
            ])
            if cross_pick not in tech:
                tech.append(cross_pick)

        # domain_tag on the project is the project's *source* domain
        # (its natural area), NOT the student's label. This is the key
        # anti-leakage move: project domain_tag != student domain_label
        # in the noisy case.
        out.append({
            "title": title,
            "description": desc,
            "tech_stack": tech,
            "domain_tag": src,
        })
    return out


def choose_skill_set(dominant_skill_domain: str, label_domain: str,
                     noisy: bool) -> list[str]:
    """Sample a skill set biased toward the dominant skill domain but
    deliberately polluted with:
      - 1-2 neighbor-domain signature skills
      - 2-3 cross-domain shared skills (e.g. Python, SQL, Git)
      - 1-2 universal soft skills (Communication, Teamwork, ...)
    so the skill list is not a 1:1 fingerprint of the label."""
    pool = list(eligible_skills_for(dominant_skill_domain))
    # Number of skills total: 5-9
    n_total = random.randint(5, 9)
    chosen = set(random.sample(pool, min(n_total, len(pool))))

    # Inject neighbor-domain signature skills
    if random.random() < 0.55:
        nbr_pool = []
        for nbr in NEIGHBOR_DOMAINS[dominant_skill_domain]:
            nbr_pool.extend(SIGNATURE_SKILLS[nbr])
        nbr_pool = list(set(nbr_pool) - chosen)
        if nbr_pool:
            k = random.randint(1, 2)
            chosen.update(random.sample(nbr_pool, min(k, len(nbr_pool))))

    # Inject a universal soft skill (always at least one)
    soft_pool = ["Communication", "Teamwork", "Problem Solving",
                 "Agile Methodology", "Time Management",
                 "Presentation Skills"]
    chosen.add(random.choice(soft_pool))

    # If noisy, also reduce dominance of the "correct" signature
    if noisy and random.random() < 0.5:
        # Replace one signature of the *label* domain with a neighbor
        # signature to weaken the direct signal.
        label_sigs = list(set(SIGNATURE_SKILLS[label_domain]) & chosen)
        if label_sigs:
            victim = random.choice(label_sigs)
            chosen.discard(victim)
            nbr_sigs = []
            for nbr in NEIGHBOR_DOMAINS[label_domain]:
                nbr_sigs.extend(SIGNATURE_SKILLS[nbr])
            nbr_sigs = [s for s in nbr_sigs if s not in chosen]
            if nbr_sigs:
                chosen.add(random.choice(nbr_sigs))

    return list(chosen)


# ==========================================================================
# Main entry point
# ==========================================================================
def generate_synthetic_data(num_students=400, num_jobs=40,
                            regenerate_students=True,
                            regenerate_jobs=True,
                            seed: int = 2025):
    seed_random(seed)
    db = SessionLocal()
    try:
        print("\n========================================================")
        print(f"  SYNTHETIC DATA GENERATOR v2: {num_students} students, {num_jobs} jobs")
        print("  (anti-leakage: shared skills, noisy labels, varied resumes)")
        print("========================================================\n")

        # 1. Default demo accounts (idempotent)
        default_pwd_hash = hash_pw("password123")

        admin = db.query(User).filter_by(email="admin@placematch.edu").first()
        if not admin:
            admin = User(
                email="admin@placematch.edu",
                hashed_password=default_pwd_hash,
                role=UserRole.ADMIN,
                full_name="College Placement Officer",
                is_active=True,
            )
            db.add(admin)

        recruiter_user = db.query(User).filter_by(email="recruiter@google.com").first()
        if not recruiter_user:
            recruiter_user = User(
                email="recruiter@google.com",
                hashed_password=default_pwd_hash,
                role=UserRole.RECRUITER,
                full_name="Tech Recruiter (Google)",
                is_active=True,
            )
            db.add(recruiter_user)

        student_user = db.query(User).filter_by(email="student@placematch.edu").first()
        if not student_user:
            student_user = User(
                email="student@placematch.edu",
                hashed_password=default_pwd_hash,
                role=UserRole.STUDENT,
                full_name="Alex Sharma",
                is_active=True,
            )
            db.add(student_user)

        db.commit()

        # 2. Companies (idempotent)
        companies = []
        for name, ind, web, email, loc in COMPANY_DATA:
            comp = db.query(Company).filter_by(company_name=name).first()
            if not comp:
                linked_user_id = recruiter_user.id if name == "Google" else None
                comp = Company(
                    user_id=linked_user_id,
                    company_name=name,
                    industry=ind,
                    website=web,
                    contact_email=email,
                    location=loc,
                )
                db.add(comp)
            companies.append(comp)
        db.commit()

        # 3. Wipe & regenerate students if requested
        if regenerate_students:
            print("[*] Wiping existing StudentProject + Student rows for clean regen...")
            # Only delete students that are not the demo linked to the manual account
            demo_user_id = student_user.id
            demo_student = db.query(Student).filter_by(user_id=demo_user_id).first()
            if demo_student:
                # Detach the demo so we can delete all others
                db.query(StudentProject).filter(StudentProject.student_id != demo_student.id).delete()
                db.query(Student).filter(Student.id != demo_student.id).delete()
                # Reset demo's AI fields so the model can re-predict
                demo_student.predicted_domain = None
                demo_student.domain_confidence = None
                # Keep demo's domain_label intact
            else:
                db.query(StudentProject).delete()
                db.query(Student).delete()
            db.commit()

        # Ensure demo student exists (overwrite for consistency)
        demo_student = db.query(Student).filter_by(user_id=student_user.id).first()
        if not demo_student:
            demo_student = Student(
                user_id=student_user.id,
                roll_number="CS2025001",
                department="Computer Science & Engineering",
                batch_year=2025,
                cgpa=Decimal("8.85"),
                active_backlogs=0,
                history_backlogs=0,
                phone="9876543210",
                gender="Male",
                category="General",
                skills=["Python", "FastAPI", "React", "PostgreSQL", "Docker", "PyTorch",
                        "Communication", "Teamwork"],
                raw_resume_text=(
                    "Candidate: Alex Sharma\n"
                    "Domain Focus: Software Development\n"
                    "Summary: Dedicated engineering undergraduate with practical "
                    "experience in software development technologies. Hands-on academic "
                    "and self-initiated projects in the software development space. "
                    "Strong communication and presentation skills. Team player with "
                    "proven collaboration across cross-functional teams. "
                    "Committed to writing clean, maintainable, well-documented code."
                ),
                domain_label="Software Development",
                predicted_domain=None,
                domain_confidence=None,
            )
            db.add(demo_student)
            db.flush()
        else:
            demo_student.skills = ["Python", "FastAPI", "React", "PostgreSQL", "Docker",
                                    "PyTorch", "Communication", "Teamwork"]
            demo_student.raw_resume_text = (
                "Candidate: Alex Sharma\n"
                "Domain Focus: Software Development\n"
                "Summary: Dedicated engineering undergraduate with practical "
                "experience in software development technologies. Hands-on academic "
                "and self-initiated projects in the software development space. "
                "Strong communication and presentation skills. Team player with "
                "proven collaboration across cross-functional teams. "
                "Committed to writing clean, maintainable, well-documented code."
            )
            demo_student.domain_label = "Software Development"
            demo_student.predicted_domain = None
            demo_student.domain_confidence = None
            db.flush()

        # Rebuild demo projects
        db.query(StudentProject).filter(StudentProject.student_id == demo_student.id).delete()
        db.add_all([
            StudentProject(
                student_id=demo_student.id,
                title="AI Campus Placement Portal",
                description=("Built full-stack recruitment matching portal using "
                              "FastAPI, React, and MySQL with explainable candidate "
                              "ranking."),
                tech_stack=["Python", "FastAPI", "React", "MySQL"],
                github_url="https://github.com/alexsharma/placematch",
                domain_tag="Software Development",
            ),
            StudentProject(
                student_id=demo_student.id,
                title="Real-time Microservices E-Commerce",
                description=("Engineered high-throughput checkout service handling "
                              "1000 RPS with Redis caching."),
                tech_stack=["Python", "Docker", "Redis", "PostgreSQL"],
                github_url="https://github.com/alexsharma/ecommerce-backend",
                domain_tag="Software Development",
            ),
        ])
        db.commit()

        # 4. Generate the 400 students
        existing_student_count = db.query(Student).count()
        students_to_generate = max(0, num_students - existing_student_count)

        dept_codes = {
            "Computer Science & Engineering": "CS",
            "Information Technology": "IT",
            "Electronics & Communication Engineering": "EC",
            "Artificial Intelligence & Data Science": "AD",
        }

        print(f"\n[*] Generating {students_to_generate} students "
              f"(target total {num_students})...")
        noisy_count = 0

        for i in range(1, students_to_generate + 1):
            # The "skill domain" — what their resume *signals* they are.
            skill_domain = random.choice(DOMAINS)

            # Decide whether to make this a noisy student (label != skill_domain)
            noisy = random.random() < NOISY_LABEL_PROBABILITY
            label_domain = (random.choice(NEIGHBOR_DOMAINS[skill_domain])
                            if noisy else skill_domain)
            if noisy:
                noisy_count += 1

            first_name = fake.first_name()
            last_name = fake.last_name()
            full_name = f"{first_name} {last_name}"
            email = f"{first_name.lower()}.{last_name.lower()}_{i}@placematch.edu"

            u = User(
                email=email,
                hashed_password=default_pwd_hash,
                role=UserRole.STUDENT,
                full_name=full_name,
                is_active=True,
            )
            db.add(u)
            db.flush()

            # CGPA + backlogs
            cgpa_val = round(min(9.8, max(5.5, random.gauss(7.4, 0.95))), 2)
            active_backlogs = random.choices([0, 1, 2, 3], weights=[85, 10, 3, 2])[0]
            history_backlogs = active_backlogs + (random.randint(0, 2) if random.random() < 0.2 else 0)

            # Skills (driven by *skill* domain, not label — so noisy
            # students get skills that don't perfectly match their label)
            chosen_skills = choose_skill_set(skill_domain, label_domain, noisy)

            # Resume style + soft-skill block
            style = pick_resume_style()
            include_soft = random.random() < SOFT_SKILL_TEXT_PROBABILITY
            resume_text = build_resume_text(
                name=full_name,
                domain=label_domain,  # header matches the *label* (GT)
                dept=random.choice(DEPARTMENTS),
                cgpa=cgpa_val,
                chosen_skills=chosen_skills,
                style=style,
                include_soft_block=include_soft,
            )

            dept = random.choice(DEPARTMENTS)
            dept_code = dept_codes.get(dept, "CS")
            roll_number = f"2021{dept_code}{1000 + i}"

            student = Student(
                user_id=u.id,
                roll_number=roll_number,
                department=dept,
                batch_year=random.choice([2024, 2025]),
                cgpa=Decimal(str(cgpa_val)),
                active_backlogs=active_backlogs,
                history_backlogs=history_backlogs,
                phone=f"9{random.randint(100000000, 999999999)}",
                gender=random.choice(["Male", "Female"]),
                category=random.choices(CATEGORIES, weights=CATEGORY_WEIGHTS)[0],
                skills=chosen_skills,
                raw_resume_text=resume_text,
                domain_label=label_domain,
                predicted_domain=None,
                domain_confidence=None,
            )
            db.add(student)
            db.flush()

            # Projects: drawn from skill_domain, with neighbor drift for noisy
            num_projects = random.randint(2, 3)
            proj_dicts = build_projects(
                student_name=full_name,
                dominant_skill_domain=skill_domain,
                label_domain=label_domain,
                num_projects=num_projects,
                noisy=noisy,
            )
            for pd in proj_dicts:
                db.add(StudentProject(
                    student_id=student.id,
                    title=pd["title"],
                    description=pd["description"],
                    tech_stack=pd["tech_stack"],
                    github_url=f"https://github.com/{first_name.lower()}/"
                               f"{pd['title'].lower().replace(' ', '-')[:40]}",
                    live_url=(f"https://{first_name.lower()}-"
                              f"{pd['title'].lower().replace(' ', '-')[:30]}.vercel.app"
                              if random.random() > 0.5 else None),
                    domain_tag=pd["domain_tag"],
                ))

            if i % 50 == 0:
                db.commit()
                print(f"   -> {i} / {students_to_generate} inserted (noisy so far: {noisy_count})")

        db.commit()
        print(f"\n[*] Student generation complete. Noisy-label students: "
              f"{noisy_count} / {students_to_generate} ({noisy_count/students_to_generate*100:.1f}%)")

        # 5. Job postings
        if regenerate_jobs:
            print(f"\n[*] Regenerating {num_jobs} job postings...")
            existing_job_count = db.query(JobPosting).count()
            jobs_to_generate = max(0, num_jobs - existing_job_count)
            # Wipe old jobs only if we have more than we need (preserves history otherwise)
            if db.query(JobPosting).count() > num_jobs:
                db.query(JobPosting).delete()
                db.commit()
                jobs_to_generate = num_jobs

            job_titles = {
                "Software Development": ["Associate Software Engineer", "Full Stack Developer",
                                          "Backend Engineer", "Junior Python Developer"],
                "Data Science / AI": ["Junior Data Scientist", "AI/ML Engineer",
                                        "Data Analyst - Campus", "Computer Vision Specialist"],
                "Quality Assurance & Testing": ["SDET - QA Engineer", "Software Test Automation Engineer",
                                                  "Quality Assurance Analyst"],
                "DevOps & Cloud Engineering": ["Cloud Infrastructure Associate", "DevOps Engineer (Trainee)",
                                                 "Site Reliability Engineer"],
                "Technical Support & Cybersecurity": ["Cybersecurity Analyst", "IT Operations Engineer",
                                                       "Technical Support Engineer"],
            }

            all_companies = db.query(Company).all()
            for j in range(1, jobs_to_generate + 1):
                domain = random.choice(DOMAINS)
                comp = random.choice(all_companies)
                title = random.choice(job_titles[domain])

                # Mix in some cross-domain skills in requirements to make
                # matching non-trivial too.
                domain_pool = eligible_skills_for(domain)
                n_req = random.randint(3, 5)
                req_skills = random.sample(domain_pool, min(n_req, len(domain_pool)))

                # Preferred skills drawn from neighbor-domain pools
                pref_pool = []
                for nbr in NEIGHBOR_DOMAINS[domain]:
                    pref_pool.extend(SIGNATURE_SKILLS[nbr])
                pref_pool = list(set(pref_pool) - set(req_skills))
                pref_skills = random.sample(pref_pool, min(3, len(pref_pool))) if pref_pool else []

                min_cgpa = Decimal(str(random.choice([6.00, 6.50, 7.00, 7.50, 8.00])))
                max_backlogs = random.choice([0, 0, 0, 1])
                buffer_pct = float(random.choice([5.0, 10.0, 15.0]))

                job = JobPosting(
                    company_id=comp.id,
                    title=f"{title} ({comp.company_name})",
                    target_domain=domain,
                    description=(f"{comp.company_name} is hiring {title} graduates for our "
                                  f"{comp.location} engineering teams. We look for candidates "
                                  f"proficient in {', '.join(req_skills)} with strong problem "
                                  f"solving and project execution capabilities."),
                    min_cgpa=min_cgpa,
                    max_backlogs_allowed=max_backlogs,
                    required_skills=req_skills,
                    preferred_skills=pref_skills,
                    salary_range=random.choice(["6 - 9 LPA", "8 - 12 LPA", "10 - 15 LPA",
                                                 "12 - 18 LPA", "18 - 24 LPA"]),
                    location=comp.location,
                    status=JobStatus.ACTIVE,
                    buffer_threshold_percent=buffer_pct,
                )
                db.add(job)

            db.commit()

        # 6. Sanity check
        total_users = db.query(User).count()
        total_students = db.query(Student).count()
        total_projects = db.query(StudentProject).count()
        total_companies = db.query(Company).count()
        total_jobs = db.query(JobPosting).count()
        total_labeled = db.query(Student).filter(Student.domain_label.isnot(None)).count()

        print("\n========================================================")
        print("  SYNTHETIC DATA GENERATION COMPLETE (v2)")
        print("========================================================")
        print(f" Users:         {total_users}")
        print(f" Students:      {total_students}  (labeled: {total_labeled})")
        print(f" Projects:      {total_projects}")
        print(f" Companies:     {total_companies}")
        print(f" Job Postings:  {total_jobs}")
        print("--------------------------------------------------------")
        print(" Demo logins:")
        print("   admin@placematch.edu       / password123")
        print("   recruiter@google.com       / password123")
        print("   student@placematch.edu     / password123")
        print("========================================================\n")
        return True

    except Exception as e:
        db.rollback()
        print(f"[!] Error generating synthetic data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-students", type=int, default=400)
    parser.add_argument("--num-jobs", type=int, default=40)
    parser.add_argument("--seed", type=int, default=2025)
    parser.add_argument("--no-regen-students", action="store_true")
    parser.add_argument("--no-regen-jobs", action="store_true")
    args = parser.parse_args()

    generate_synthetic_data(
        num_students=args.num_students,
        num_jobs=args.num_jobs,
        regenerate_students=not args.no_regen_students,
        regenerate_jobs=not args.no_regen_jobs,
        seed=args.seed,
    )
