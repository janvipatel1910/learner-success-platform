# SkillPulse Learner Success OS

## Project Status

- Working name: SkillPulse Learner Success OS
- Repository: learner-success-platform
- Product owner and lead developer: Janvi Patel
- Project type: Data-driven EdTech and learner-success platform
- Initial use case: AWS and DevOps training cohorts
- Potential pilot organisation: UpSkills, subject to written permission

## 1. Purpose

SkillPulse is not a generic course-uploading LMS. It is a learner-success operating system that helps students, tutors and training administrators identify learning difficulties early, resolve blockers and measure whether support improved learner outcomes.

The platform will combine software development, data analytics, AWS, DevOps and verified-source AI.

## 2. Problem Statement

Training providers commonly store recordings, notes, assignments and quiz results in separate places. Tutors cannot easily identify:

- Which learners did not understand a class
- Which topics are weak across the cohort
- Which students have unresolved blockers
- Whether tutor support improved performance
- Whether a learner is genuinely exam-ready
- Why a learner is considered ready or not ready

Students may feel confident after class but later struggle with mock questions or hands-on labs. Existing completion percentages do not explain this confidence-versus-competence gap.

## 3. Primary Users

### Student

The student needs one place to access materials, submit labs, complete quizzes, report blockers and receive an evidence-based readiness plan.

### Tutor

The tutor needs to identify learners requiring support, respond to blockers, monitor topic weaknesses and verify whether interventions worked.

### Administrator

The administrator needs cohort-level analytics covering attendance, engagement, weak topics, unresolved blockers, certificate eligibility and exam readiness.

## 4. Unique Product Value

SkillPulse will create a closed learner-intervention loop:

1. Student attends a class
2. Student submits a Green, Yellow or Red understanding check
3. Quiz, lab and attendance evidence is collected
4. The system identifies confidence and performance gaps
5. A learner blocker or tutor intervention is created
6. The tutor responds and records the resolution
7. The student repeats the relevant quiz or lab
8. The system measures improvement and updates readiness

The platform will not only show what happened. It will recommend the next useful action and explain why.

## 5. Core MVP Features

- Student, tutor and administrator login
- Cohort and course management
- Recordings, PDFs, notes and assignments
- Hands-on AWS lab submission
- Topic-based quizzes
- Original 65-question timed mock exams
- Green, Yellow and Red post-class understanding checks
- Student blocker and support-request workflow
- Tutor response and resolution tracking
- Explainable exam-readiness score
- Confidence-versus-competence gap detection
- Certificate eligibility tracker
- Admin learner-success analytics
- Excel import and export
- Power BI reporting dataset
- Verified-source AI tutor with citations

## 6. Data and Analytics Components

### Excel

- Student roster import
- Attendance templates
- Question-bank review
- Administrative exports
- Manual quality checks

### Python

- FastAPI backend
- Data validation and cleaning
- Readiness-score calculation
- Learner-risk indicators
- Analytics pipeline
- Automated reports

### SQL

- Operational PostgreSQL database
- Topic-mastery queries
- Learner-progress analysis
- Blocker-resolution analysis
- Cohort comparison
- Analytics views for Power BI

### Power BI

- Executive overview
- Exam-readiness dashboard
- Weak-topic analysis
- Attendance and engagement
- Blocker and tutor-response analytics
- Certificate eligibility

## 7. Success Metrics

Pilot results will be measured using real baseline and follow-up data. No impact figures will be claimed without evidence.

Metrics will include:

- Weekly and monthly active learners
- Course and lab completion rate
- Quiz and mock-score improvement
- Topic-mastery improvement
- Number of open and resolved blockers
- Average tutor first-response time
- Average blocker-resolution time
- Learner recovery after intervention
- Tutor administrative time saved
- Certificate-eligible learners
- Verified AI answers and tutor escalations

## 8. Responsible Data Rules

- No real student personal data will be committed to GitHub
- Development will use anonymised or synthetic data
- Role-based access will restrict student, tutor and admin information
- Analytics will use learner IDs instead of unnecessary personal details
- UpSkills branding, course materials and learner data require written permission
- Official AWS exam questions will not be copied
- AI answers must use approved sources and display citations
- AI must not guess when an answer cannot be verified
- Readiness indicators support tutors and learners; they do not punish students or guarantee exam success

## 9. Technology Direction

- Frontend: React
- Backend: Python and FastAPI
- Database: PostgreSQL
- Analytics: Python, SQL, Excel and Power BI
- Cloud: AWS
- DevOps: Git, GitHub Actions, Docker, Terraform, testing and monitoring
- AI: Retrieval from verified course sources with citations

## 10. Initial Scope Boundaries

The first release will focus on one AWS cohort and a limited number of topics. It will not initially include:

- Payments or finance
- Public social networking
- Multiple unrelated training industries
- Automated high-stakes student decisions
- Unverified general-purpose AI answers
- UpSkills branding without approval

## 11. Definition of a Strong Completed Project

The project will be considered strongly completed when:

- The production application is deployed
- Core workflows are tested
- Security and monitoring are configured
- Technical architecture and decisions are documented
- GitHub history clearly shows Janvi Patel's contribution
- A real or formally approved pilot is completed
- Before-and-after metrics are collected
- Learner and tutor feedback is documented
- A case study explains the problem, solution and measured results
