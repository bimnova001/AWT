from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageType(str, Enum):

    TASK_OFFER = "TASK_OFFER"

    TASK_ACCEPTED = "TASK_ACCEPTED"

    TASK_REJECTED = "TASK_REJECTED"

    TASK_RESULT = "TASK_RESULT"

    REVIEW_REQUEST = "REVIEW_REQUEST"

    REVIEW_RESULT = "REVIEW_RESULT"

    SUBTASK_CREATED = "SUBTASK_CREATED"

    QUESTION = "QUESTION"

    ANSWER = "ANSWER"

    ERROR = "ERROR"


class AgentMessage(BaseModel):

    message_id: str

    from_agent: str

    to_agent: str | None

    type: MessageType

    task_id: str | None = None

    reply_to: str | None = None

    payload: dict[str, Any] = Field(
        default_factory=dict
    )