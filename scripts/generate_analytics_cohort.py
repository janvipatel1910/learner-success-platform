"""Generate a larger synthetic cohort for testing SkillPulse analytics.

The original seed has two learners, which is too few for meaningful
dashboards. This script writes a SQL file with a separate demo course,
five topics and 40 fictional learners who follow different learning
patterns (strong, steady, overconfident, underconfident, struggling).

All people and activity are fictional. The output is deterministic:
the same seed always produces the same SQL, and fixed UUIDs with
ON CONFLICT DO NOTHING make the file safe to load more than once.

Usage:
    python scripts/generate_analytics_cohort.py
Then load the file into a local (non-production) database.
"""

from __future__ import annotations

import json
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

RANDOM_SEED = 42
LEARNER_COUNT = 40
QUESTIONS_PER_TOPIC = 8
WRONG_OPTIONS = ["Option B", "Option C", "Option D"]

OUTPUT_FILE = (
    Path(__file__).resolve().parents[1] / "data" / "sample" / "skillpulse_analytics_cohort.sql"
)

# Fixed namespace so every generated UUID is stable between runs.
NAMESPACE = uuid.UUID("5b1c0d7e-2f3a-4c6b-9e8d-7a6b5c4d3e2f")

ORGANIZATION_ID = "10000000-0000-0000-0000-000000000001"
ADMIN_ID = "20000000-0000-0000-0000-000000000001"
EXISTING_TUTOR_ID = "20000000-0000-0000-0000-000000000002"
READINESS_MODEL_ID = "80000000-0000-0000-0000-000000000001"
COURSE_DESCRIPTION = "Synthetic course for testing SkillPulse analytics at cohort scale."

COHORT_START = datetime(2026, 9, 1, tzinfo=UTC)
COHORT_END = datetime(2026, 11, 14, tzinfo=UTC)

# difficulty_shift lowers or raises the chance of a correct answer.
TOPICS = [
    ("IAM and Security", "Design Secure Architectures", 0),
    ("Networking and VPC", "Design Secure Architectures", -18),
    ("Compute and EC2", "Design High-Performing Architectures", 5),
    ("Storage and S3", "Design Resilient Architectures", 6),
    ("Databases and RDS", "Design Resilient Architectures", -8),
]

# skill: base % correct, confidence: how they rate themselves,
# attendance: chance of attending a session.
ARCHETYPES = {
    "strong": {"skill": 85, "confidence": "high", "attendance": 0.95},
    "steady": {"skill": 68, "confidence": "medium", "attendance": 0.85},
    "overconfident": {"skill": 48, "confidence": "high", "attendance": 0.75},
    "underconfident": {"skill": 78, "confidence": "low", "attendance": 0.9},
    "struggling": {"skill": 38, "confidence": "low", "attendance": 0.55},
}
ARCHETYPE_MIX = (
    ["strong"] * 11
    + ["steady"] * 12
    + ["overconfident"] * 6
    + ["underconfident"] * 4
    + ["struggling"] * 7
)

# Average extra improvement after each type of tutor support.
INTERVENTION_GAINS = {
    "one_to_one_support": 24,
    "targeted_practice": 15,
    "peer_session": 7,
}


def make_id(name: str) -> str:
    return str(uuid.uuid5(NAMESPACE, name))


def ts(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def sql_value(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        return f"'{ts(value)}'"
    if isinstance(value, (list, dict)):
        value = json.dumps(value)
    return "'" + str(value).replace("'", "''") + "'"


def insert(table: str, rows: list[dict[str, object]]) -> str:
    if not rows:
        return ""
    columns = list(rows[0].keys())
    lines = [
        "    (" + ", ".join(sql_value(row[column]) for column in columns) + ")" for row in rows
    ]
    return (
        f"INSERT INTO {table} ({', '.join(columns)})\nVALUES\n"
        + ",\n".join(lines)
        + "\nON CONFLICT DO NOTHING;\n\n"
    )


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


@dataclass
class Learner:
    number: int
    archetype: str
    tutor_id: str
    id: str = ""
    attended: int = 0
    sessions: int = 0
    topic_scores: dict[str, float] = field(default_factory=dict)
    open_blockers: int = 0
    lab_score: float = 0

    def __post_init__(self) -> None:
        self.id = make_id(f"learner-{self.number}")


def rating_for(learner: Learner, rng: random.Random, topic_shift: int) -> str:
    style = ARCHETYPES[learner.archetype]["confidence"]
    roll = rng.random() + topic_shift / 100
    if style == "high":
        return "green" if roll > 0.2 else "yellow"
    if style == "low":
        return "red" if roll < 0.45 else "yellow"
    return "green" if roll > 0.55 else ("yellow" if roll > 0.15 else "red")


def readiness_level(score: float) -> str:
    if score >= 75:
        return "ready"
    if score >= 60:
        return "nearly_ready"
    if score >= 40:
        return "developing"
    return "not_ready"


def build_sql() -> str:
    rng = random.Random(RANDOM_SEED)
    sql: list[str] = [
        "-- SkillPulse synthetic ANALYTICS cohort (generated file).\n"
        "-- Created by scripts/generate_analytics_cohort.py - do not edit by hand.\n"
        "-- All people, emails and activity below are fictional.\n"
        "-- Load into local or demo databases only, never with real learners.\n\n"
        "BEGIN;\n\n"
    ]

    course_id = make_id("course")
    cohort_id = make_id("cohort")
    source_id = make_id("verified-source")
    second_tutor_id = make_id("tutor-2")
    tutor_ids = [EXISTING_TUTOR_ID, second_tutor_id]

    # --- Course structure ---
    sql.append(
        insert(
            "users",
            [
                {
                    "id": second_tutor_id,
                    "email": "tutor.two@analytics.skillpulse.example",
                    "full_name": "Synthetic Tutor Two",
                    "status": "active",
                }
            ],
        )
    )
    sql.append(
        insert(
            "organization_memberships",
            [
                {
                    "id": make_id("org-membership-tutor-2"),
                    "organization_id": ORGANIZATION_ID,
                    "user_id": second_tutor_id,
                    "role": "tutor",
                    "status": "active",
                    "joined_at": COHORT_START - timedelta(days=7),
                }
            ],
        )
    )
    sql.append(
        insert(
            "courses",
            [
                {
                    "id": course_id,
                    "organization_id": ORGANIZATION_ID,
                    "title": "AWS Solutions Architect Analytics Demo",
                    "code": "AWS-SAA-ANALYTICS",
                    "description": COURSE_DESCRIPTION,
                    "certification_name": "AWS Certified Solutions Architect - Associate",
                    "status": "active",
                }
            ],
        )
    )

    topic_ids: list[str] = []
    topic_rows = []
    for number, (title, domain, _shift) in enumerate(TOPICS, start=1):
        topic_id = make_id(f"topic-{number}")
        topic_ids.append(topic_id)
        topic_rows.append(
            {
                "id": topic_id,
                "course_id": course_id,
                "title": title,
                "sequence_number": number,
                "exam_domain": domain,
                "expected_hours": 6,
            }
        )
    sql.append(insert("topics", topic_rows))

    sql.append(
        insert(
            "cohorts",
            [
                {
                    "id": cohort_id,
                    "course_id": course_id,
                    "name": "Synthetic Analytics Cohort 2026",
                    "start_date": COHORT_START.date().isoformat(),
                    "end_date": COHORT_END.date().isoformat(),
                    "delivery_mode": "online",
                    "status": "completed",
                }
            ],
        )
    )

    sql.append(
        insert(
            "verified_sources",
            [
                {
                    "id": source_id,
                    "course_id": course_id,
                    "title": "AWS Architecture Documentation",
                    "source_type": "official_documentation",
                    "source_url": "https://docs.aws.amazon.com/",
                    "document_version": "synthetic-analytics-v1",
                    "approved_by": ADMIN_ID,
                    "approved_at": COHORT_START - timedelta(days=7),
                    "status": "active",
                    "checksum": "skillpulse-synthetic-analytics-v1",
                }
            ],
        )
    )

    question_ids: dict[str, list[str]] = {}
    question_rows = []
    assessment_rows = []
    for t_index, topic_id in enumerate(topic_ids):
        title = TOPICS[t_index][0]
        question_ids[topic_id] = []
        for q in range(1, QUESTIONS_PER_TOPIC + 1):
            question_id = make_id(f"question-{t_index}-{q}")
            question_ids[topic_id].append(question_id)
            question_rows.append(
                {
                    "id": question_id,
                    "topic_id": topic_id,
                    "question_text": f"Synthetic {title} question {q}",
                    "question_type": "single_choice",
                    "options_json": ["Option A", "Option B", "Option C", "Option D"],
                    "correct_answer_json": ["Option A"],
                    "explanation": "Synthetic question used for analytics testing.",
                    "difficulty": 3,
                    "verified_source_id": source_id,
                    "status": "published",
                }
            )
        assessment_rows.append(
            {
                "id": make_id(f"assessment-{t_index}"),
                "course_id": course_id,
                "title": f"{title} Topic Quiz",
                "assessment_type": "quiz",
                "question_count": QUESTIONS_PER_TOPIC,
                "time_limit_minutes": 15,
                "pass_percentage": 70,
                "maximum_attempts": 3,
                "status": "published",
                "published_at": COHORT_START,
            }
        )
    sql.append(insert("questions", question_rows))
    sql.append(insert("assessments", assessment_rows))

    # --- Two class sessions per topic, one week apart ---
    session_rows = []
    sessions_by_topic: dict[str, list[tuple[str, datetime]]] = {}
    session_start = COHORT_START + timedelta(days=1, hours=18)
    for t_index, topic_id in enumerate(topic_ids):
        sessions_by_topic[topic_id] = []
        for part in (1, 2):
            session_id = make_id(f"session-{t_index}-{part}")
            sessions_by_topic[topic_id].append((session_id, session_start))
            session_rows.append(
                {
                    "id": session_id,
                    "cohort_id": cohort_id,
                    "topic_id": topic_id,
                    "title": f"{TOPICS[t_index][0]} - Part {part}",
                    "scheduled_start": session_start,
                    "scheduled_end": session_start + timedelta(hours=2),
                    "status": "completed",
                }
            )
            session_start += timedelta(days=7)
    sql.append(insert("class_sessions", session_rows))

    # --- Learners and memberships ---
    archetypes = ARCHETYPE_MIX[:]
    rng.shuffle(archetypes)
    learners = [
        Learner(number=n, archetype=archetypes[n - 1], tutor_id=tutor_ids[n % 2])
        for n in range(1, LEARNER_COUNT + 1)
    ]

    sql.append(
        insert(
            "users",
            [
                {
                    "id": learner.id,
                    "email": f"learner{learner.number:02d}@analytics.skillpulse.example",
                    "full_name": f"Synthetic Learner {learner.number:02d}",
                    "status": "active",
                }
                for learner in learners
            ],
        )
    )
    sql.append(
        insert(
            "organization_memberships",
            [
                {
                    "id": make_id(f"org-membership-{learner.number}"),
                    "organization_id": ORGANIZATION_ID,
                    "user_id": learner.id,
                    "role": "student",
                    "status": "active",
                    "joined_at": COHORT_START - timedelta(days=3),
                }
                for learner in learners
            ],
        )
    )

    membership_rows = [
        {
            "id": make_id(f"cohort-membership-tutor-{i}"),
            "cohort_id": cohort_id,
            "user_id": tutor_id,
            "cohort_role": "tutor",
            "status": "active",
            "enrolled_at": COHORT_START - timedelta(days=7),
        }
        for i, tutor_id in enumerate(tutor_ids)
    ]
    membership_rows += [
        {
            "id": make_id(f"cohort-membership-{learner.number}"),
            "cohort_id": cohort_id,
            "user_id": learner.id,
            "cohort_role": "learner",
            "status": "active",
            "enrolled_at": COHORT_START - timedelta(days=3),
        }
        for learner in learners
    ]
    sql.append(insert("cohort_memberships", membership_rows))

    # --- Activity: attendance, understanding checks, quizzes, blockers ---
    attendance_rows, check_rows = [], []
    attempt_rows, response_rows = [], []
    blocker_rows, intervention_rows = [], []

    for learner in learners:
        profile = ARCHETYPES[learner.archetype]
        for t_index, topic_id in enumerate(topic_ids):
            shift = TOPICS[t_index][2]

            for session_id, start in sessions_by_topic[topic_id]:
                learner.sessions += 1
                roll = rng.random()
                if roll < profile["attendance"]:
                    status = "late" if rng.random() < 0.12 else "present"
                    minutes = rng.randint(70, 110) if status == "late" else rng.randint(110, 120)
                    learner.attended += 1
                    check_rows.append(
                        {
                            "id": make_id(f"check-{learner.number}-{session_id}"),
                            "session_id": session_id,
                            "learner_id": learner.id,
                            "rating": rating_for(learner, rng, shift),
                            "comment": None,
                            "submitted_at": start + timedelta(hours=2, minutes=10),
                        }
                    )
                else:
                    status = "excused" if rng.random() < 0.2 else "absent"
                    minutes = 0
                attendance_rows.append(
                    {
                        "id": make_id(f"attendance-{learner.number}-{session_id}"),
                        "session_id": session_id,
                        "learner_id": learner.id,
                        "attendance_status": status,
                        "minutes_attended": minutes,
                        "recorded_by": learner.tutor_id,
                        "recorded_at": start + timedelta(hours=2, minutes=5),
                    }
                )

            # Topic quiz, taken a few days after the second session.
            quiz_time = sessions_by_topic[topic_id][1][1] + timedelta(days=rng.randint(1, 4))
            chance = clamp(profile["skill"] + shift + rng.gauss(0, 8), 5, 98) / 100
            attempt_id = make_id(f"attempt-{learner.number}-{t_index}")
            correct = 0
            for question_id in question_ids[topic_id]:
                is_correct = rng.random() < chance
                correct += is_correct
                response_rows.append(
                    {
                        "id": make_id(f"response-{learner.number}-{question_id}"),
                        "attempt_id": attempt_id,
                        "question_id": question_id,
                        "selected_answer_json": (
                            ["Option A"] if is_correct else [rng.choice(WRONG_OPTIONS)]
                        ),
                        "is_correct": is_correct,
                        "marks_awarded": 1 if is_correct else 0,
                        "response_seconds": rng.randint(30, 150),
                    }
                )
            percentage = round(100 * correct / QUESTIONS_PER_TOPIC, 2)
            learner.topic_scores[topic_id] = percentage
            attempt_rows.append(
                {
                    "id": attempt_id,
                    "assessment_id": make_id(f"assessment-{t_index}"),
                    "learner_id": learner.id,
                    "attempt_number": 1,
                    "started_at": quiz_time,
                    "submitted_at": quiz_time + timedelta(minutes=rng.randint(6, 14)),
                    "score": correct,
                    "percentage": percentage,
                    "passed": percentage >= 70,
                    "status": "submitted",
                }
            )

            # Low scores often lead to a blocker and tutor support.
            if percentage < 55 and rng.random() < 0.7:
                blocker_id = make_id(f"blocker-{learner.number}-{t_index}")
                opened = quiz_time + timedelta(days=1, hours=rng.randint(0, 8))
                is_open = rng.random() < 0.25
                if is_open:
                    learner.open_blockers += 1
                    blocker_status = rng.choice(["open", "assigned", "waiting_student"])
                    resolved_at = None
                    summary = None
                else:
                    blocker_status = "resolved"
                    resolved_at = opened + timedelta(days=rng.randint(2, 9))
                    summary = "Learner completed follow-up practice with tutor support."
                blocker_rows.append(
                    {
                        "id": blocker_id,
                        "learner_id": learner.id,
                        "cohort_id": cohort_id,
                        "topic_id": topic_id,
                        "title": f"Difficulty with {TOPICS[t_index][0]}",
                        "description": "Synthetic blocker raised after a low topic quiz score.",
                        "category": "concept",
                        "severity": "high" if percentage < 35 else "medium",
                        "status": blocker_status,
                        "assigned_tutor_id": None if blocker_status == "open" else learner.tutor_id,
                        "opened_at": opened,
                        "resolved_at": resolved_at,
                        "resolution_summary": summary,
                    }
                )

                if blocker_status != "open":
                    kind = rng.choice(list(INTERVENTION_GAINS))
                    started = opened + timedelta(hours=rng.randint(4, 30))
                    if resolved_at is None:
                        follow_up, outcome, completed = None, "pending", None
                    else:
                        gain = INTERVENTION_GAINS[kind] + rng.gauss(0, 8)
                        follow_up = round(clamp(percentage + gain), 2)
                        outcome = "improved" if follow_up - percentage >= 5 else "no_change"
                        completed = max(resolved_at, started + timedelta(hours=1))
                    intervention_rows.append(
                        {
                            "id": make_id(f"intervention-{learner.number}-{t_index}"),
                            "learner_id": learner.id,
                            "cohort_id": cohort_id,
                            "topic_id": topic_id,
                            "blocker_id": blocker_id,
                            "intervention_type": kind,
                            "action_taken": f"Synthetic {kind.replace('_', ' ')}.",
                            "baseline_metric": "topic_score",
                            "baseline_value": percentage,
                            "follow_up_value": follow_up,
                            "outcome": outcome,
                            "tutor_id": learner.tutor_id,
                            "started_at": started,
                            "completed_at": completed,
                        }
                    )

    sql.append(insert("attendance_records", attendance_rows))
    sql.append(insert("understanding_checks", check_rows))
    sql.append(insert("assessment_attempts", attempt_rows))
    sql.append(insert("question_responses", response_rows))
    sql.append(insert("blockers", blocker_rows))
    sql.append(insert("tutor_interventions", intervention_rows))

    # --- Readiness: a mid-course and an end-of-course snapshot ---
    snapshot_rows, eligibility_rows = [], []
    for learner in learners:
        quiz = sum(learner.topic_scores.values()) / len(learner.topic_scores)
        attendance = 100 * learner.attended / learner.sessions
        lab = clamp(ARCHETYPES[learner.archetype]["skill"] + 5 + rng.gauss(0, 10))
        mock = clamp(quiz - 4 + rng.gauss(0, 6))
        blocker = clamp(100 - 30 * learner.open_blockers)

        for label, when, factor in (
            ("mid", datetime(2026, 10, 6, 12, tzinfo=UTC), 0.85),
            ("final", COHORT_END + timedelta(hours=12), 1.0),
        ):
            parts = {
                "quiz": round(clamp(quiz * factor), 2),
                "mock": round(clamp(mock * factor), 2),
                "lab": round(clamp(lab * factor), 2),
                "attendance": round(attendance, 2),
                "blockers": round(blocker, 2),
            }
            overall = round(
                0.20 * parts["quiz"]
                + 0.30 * parts["mock"]
                + 0.20 * parts["lab"]
                + 0.15 * parts["attendance"]
                + 0.15 * parts["blockers"],
                2,
            )
            strengths = [name for name, value in parts.items() if value >= 80]
            snapshot_id = make_id(f"readiness-{label}-{learner.number}")
            snapshot_rows.append(
                {
                    "id": snapshot_id,
                    "learner_id": learner.id,
                    "cohort_id": cohort_id,
                    "readiness_model_id": READINESS_MODEL_ID,
                    "quiz_component": parts["quiz"],
                    "mock_component": parts["mock"],
                    "lab_component": parts["lab"],
                    "attendance_component": parts["attendance"],
                    "blocker_component": parts["blockers"],
                    "overall_score": overall,
                    "readiness_level": readiness_level(overall),
                    "explanation_json": {"strengths": strengths, "snapshot": label},
                    "calculated_at": when,
                }
            )

            if label == "final":
                checks = {
                    "attendance": attendance >= 80,
                    "assignment": parts["quiz"] >= 70,
                    "lab": parts["lab"] >= 80,
                    "mock_score": parts["mock"] >= 70,
                    "open_blocker": learner.open_blockers == 0,
                    "module_checks": parts["quiz"] >= 70,
                    "final_project": overall >= 65,
                }
                eligibility_rows.append(
                    {
                        "id": make_id(f"eligibility-{learner.number}"),
                        "learner_id": learner.id,
                        "cohort_id": cohort_id,
                        "readiness_snapshot_id": snapshot_id,
                        "attendance_met": checks["attendance"],
                        "assignment_met": checks["assignment"],
                        "lab_met": checks["lab"],
                        "mock_score_met": checks["mock_score"],
                        "blockers_cleared": checks["open_blocker"],
                        "module_checks_met": checks["module_checks"],
                        "final_project_met": checks["final_project"],
                        "is_eligible": all(checks.values()),
                        "missing_requirements_json": [k for k, ok in checks.items() if not ok],
                        "evaluated_at": when + timedelta(minutes=10),
                    }
                )

    sql.append(insert("readiness_snapshots", snapshot_rows))
    sql.append(insert("certificate_eligibility", eligibility_rows))
    sql.append("COMMIT;\n")
    return "".join(sql)


def main() -> None:
    OUTPUT_FILE.write_text(build_sql(), encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
