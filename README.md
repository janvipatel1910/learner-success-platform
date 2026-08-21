# SkillPulse Learner Success OS

[![PostgreSQL Schema Validation](https://github.com/janvipatel1910/learner-success-platform/actions/workflows/schema-validation.yml/badge.svg)](https://github.com/janvipatel1910/learner-success-platform/actions/workflows/schema-validation.yml)

[![Backend CI](https://github.com/janvipatel1910/learner-success-platform/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/janvipatel1910/learner-success-platform/actions/workflows/backend-ci.yml)

A data-driven learner-success platform for AWS and DevOps training cohorts.

> **Current status:** SC-003 — containerized FastAPI backend and automated backend CI

> **Project owner and lead developer:** Janvi Patel

> **Potential pilot organisation:** UpSkills, subject to written approval

## About the Project

SkillPulse is not a generic course-uploading LMS. It is designed to identify where learners are struggling, help tutors resolve blockers and measure whether support improves learner outcomes.

The platform will combine:

- Full-stack product development
- Data analysis and business intelligence
- AWS cloud architecture
- DevOps automation
- Verified-source AI assistance

## Problem Being Solved

Traditional learning platforms normally track content completion and quiz scores. They do not clearly explain:

- Which learners did not understand a class
- Why a learner is falling behind
- Which topics are weak across a cohort
- Which support requests remain unresolved
- Whether tutor intervention improved performance
- Whether a learner is genuinely exam-ready

SkillPulse will turn learner activity into explainable support actions.

## Unique Learner-Intervention Loop

1. Student attends a class
2. Student submits a Green, Yellow or Red understanding check
3. Quiz, lab and attendance evidence is collected
4. The system detects confidence-versus-competence gaps
5. A blocker or tutor intervention is created
6. The tutor responds and records the resolution
7. The learner repeats the relevant activity
8. The platform measures improvement and updates readiness

## Primary Users

### Students

Access learning materials, complete quizzes, submit AWS labs, report blockers and receive an evidence-based revision plan.

### Tutors

Identify learners needing support, respond to blockers, review weak topics and verify whether interventions worked.

### Administrators

Monitor cohort engagement, attendance, readiness, unresolved blockers, certificate eligibility and course outcomes.

## Planned MVP Features

- Student, tutor and administrator authentication
- Cohort and course management
- Recordings, PDFs, notes and assignments
- Hands-on AWS lab submissions
- Topic-based quizzes
- Original 65-question timed mock exams
- Green, Yellow and Red class-understanding checks
- Blocker and tutor-resolution workflow
- Explainable exam-readiness score
- Confidence-versus-competence analysis
- Certificate eligibility tracker
- Admin analytics
- Excel import and export
- Power BI dashboards
- Verified-source AI tutor with citations

## Technology Stack

| Area | Technologies |
|---|---|
| Frontend | React |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| Data Analysis | Python, Pandas, SQL |
| Business Intelligence | Power BI, Excel |
| Cloud | AWS |
| DevOps | Git, GitHub Actions, Docker, Terraform |
| Testing | Pytest and frontend testing |
| AI | Retrieval from approved course sources with citations |

## Planned Data Flow

```mermaid
flowchart TD
    A["Student and Tutor App"] --> B["React Frontend"]
    B --> C["Python FastAPI"]
    C --> D["PostgreSQL"]
    D --> E["Python and SQL Analytics"]
    E --> F["Power BI Dashboards"]
    C --> G["AWS Services"]
```

## Current Implementation

| Feature | Status |
|---|---|
| SC-001 PostgreSQL product data model | Complete |
| PostgreSQL 16 execution validation | Complete |
| 29 relational tables | Complete |
| 7 analytics views | Complete |
| SC-002 reusable validation script | Implemented |
| Docker Compose development database | Implemented |
| GitHub Actions schema validation | Implemented |
| SC-003 FastAPI backend foundation | Implemented |
| PostgreSQL readiness integration | Implemented |
| Containerized non-root API service | Implemented |
| Backend quality and test CI | Implemented |
| React learner portal | Planned |
| Python analytics pipeline | Planned |
| Power BI dashboard | Planned |

## Local Development

### Requirements

- Git
- Docker Desktop
- Docker Compose

### Validate the Complete Database Schema

Run:

```bash
./scripts/validate_schema.sh
```

Expected result:

```text
Schema transaction completed successfully.
Validated tables: 29
Validated views: 7
SkillPulse schema validation PASSED.
```

The script creates an isolated PostgreSQL 16 container, validates the complete schema, checks the expected database-object counts and automatically removes the test container.

### Start the Development Database

```bash
docker compose up -d
```

Check database health:

```bash
docker compose ps
```

Stop the development database:

```bash
docker compose down
```

The local PostgreSQL service uses port `55432` by default.
### Start the Complete Application Stack

Build and start PostgreSQL and the FastAPI service:

```bash
docker compose up -d --build
```

Check container health:

```bash
docker compose ps
```

Verify API and database readiness:

```bash
curl -fsS http://127.0.0.1:8000/ready
```

Available local endpoints:

- API information: `http://127.0.0.1:8000/`
- Liveness: `http://127.0.0.1:8000/health`
- Readiness: `http://127.0.0.1:8000/ready`
- OpenAPI documentation: `http://127.0.0.1:8000/docs`

Stop the application stack without deleting the database volume:

```bash
docker compose down
```

### Run the FastAPI Source Locally

Create and activate a virtual environment, then install the project:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[dev]"
```

Start the source application:

```bash
PYTHONPATH=backend python -m uvicorn skillpulse.main:app \
  --host 127.0.0.1 \
  --port 8000
```

### Run Backend Validation

```bash
ruff check backend tests
pytest -m "not integration"
RUN_DATABASE_TESTS=true PYTHONPATH=backend pytest -m integration
```

## Repository Structure

```text
learner-success-platform/
|-- .github/
|   `-- workflows/
|       |-- backend-ci.yml
|       `-- schema-validation.yml
|-- analytics/
|   |-- excel/
|   |-- powerbi/
|   |-- python/
|   `-- sql/
|-- backend/
|   |-- database/
|   |   `-- schema.sql
|   |-- skillpulse/
|   |   |-- api/
|   |   |-- core/
|   |   |-- db/
|   |   |-- schemas/
|   |   `-- main.py
|   `-- Dockerfile
|-- data/
|   `-- sample/
|-- docs/
|   |-- PRODUCT_CHARTER.md
|   |-- DATA_MODEL.md
|   |-- SC-001_VALIDATION.md
|   |-- SC-002_SCHEMA_CI.md
|   `-- SC-003_FASTAPI_FOUNDATION.md
|-- frontend/
|-- infrastructure/
|   `-- terraform/
|-- scripts/
|   `-- validate_schema.sh
|-- tests/
|   `-- backend/
|       |-- conftest.py
|       |-- test_config.py
|       |-- test_database.py
|       `-- test_health.py
|-- .dockerignore
|-- .env.example
|-- .gitignore
|-- compose.yaml
|-- pyproject.toml
`-- README.md
```

## Database Foundation

The validated PostgreSQL design currently includes:

- Multi-organisation membership
- Student, tutor and administrator roles
- Courses, topics, cohorts and sessions
- Attendance and understanding checks
- Quizzes and 65-question mock exams
- Hands-on lab evidence
- Learner blockers and tutor interventions
- Versioned readiness models
- Explainable readiness snapshots
- Certificate eligibility
- Verified AI sources and citations
- Append-only audit history
- Analytics-ready reporting views

## Documentation

- [Product charter](docs/PRODUCT_CHARTER.md)
- [Product data model](docs/DATA_MODEL.md)
- [SC-001 PostgreSQL validation](docs/SC-001_VALIDATION.md)
- [SC-002 schema CI implementation](docs/SC-002_SCHEMA_CI.md)

- [SC-003 FastAPI backend foundation](docs/SC-003_FASTAPI_FOUNDATION.md)

## Relationship to Beginner Cloud Journey

The existing `beginner-cloud-journey` repository remains an independent AWS-learning project. SkillPulse may later reuse approved educational concepts or public learning resources, but learner records, application logic and analytics remain inside this separate product repository.

## Responsible Data Principles

- Use synthetic learner data during public development
- Never commit student personal information
- Never store AWS secret keys in lab evidence
- Restrict students to their own records
- Restrict tutors to assigned cohorts
- Keep readiness decisions explainable
- Version all readiness-scoring rules
- Record sensitive administrative actions
- Define retention and deletion procedures before a real pilot
- Obtain written permission before using UpSkills branding or course content

## Project Goal

SkillPulse will demonstrate how full-stack development, data analytics, AWS and DevOps can work together to improve real learner outcomes. Success will be measured through learner progress, blocker resolution, tutor efficiency and explainable exam readiness—not only content completion.
