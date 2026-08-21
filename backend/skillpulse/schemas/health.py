from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["healthy"]
    service: str
    version: str
    environment: str
    timestamp: datetime


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    service: str
    database: Literal["connected", "unavailable"]
    timestamp: datetime
