"""Learner module progression responses."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ModuleProgressResponse(BaseModel):
    topic_id: UUID
    title: str
    sequence_number: int
    exam_domain: str | None
    expected_hours: Decimal | None
    status: Literal[
        "locked",
        "available",
        "in_progress",
        "completed",
    ]
    started_at: datetime | None
    completed_at: datetime | None
