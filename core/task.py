from enum import Enum
from typing import Any

from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):

    CREATED = "CREATED"

    PROPOSED = "PROPOSED"

    ACCEPTED = "ACCEPTED"

    RUNNING = "RUNNING"

    REVIEW = "REVIEW"

    REWORK = "REWORK"

    COMPLETED = "COMPLETED"

    FAILED = "FAILED"

    CANCELLED = "CANCELLED"


class Task(BaseModel):

    task_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    parent_task_id: str | None = None

    description: str

    required_capabilities: list[str] = Field(
        default_factory=list
    )

    created_by: str | None = None

    assigned_agent: str | None = None

    reviewer_agent: str | None = None

    status: TaskStatus = TaskStatus.CREATED

    result: Any | None = None

    review_result: Any | None = None

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    children: list[str] = Field(
        default_factory=list
    )

    attempts: int = 0

    review_round: int = 0

    max_attempts: int = 3