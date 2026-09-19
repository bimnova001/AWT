from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    ANNOUNCE = "ANNOUNCE"
    PROPOSE_TASK = "PROPOSE_TASK"
    ACCEPT_TASK = "ACCEPT_TASK"
    REJECT_TASK = "REJECT_TASK"
    RESULT = "RESULT"
    REVIEW = "REVIEW"
    QUESTION = "QUESTION"
    DONE = "DONE"


class AgentMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid4()))

    from_agent: str
    to_agent: str | None = None

    type: MessageType

    task_id: str | None = None

    payload: dict[str, Any] = Field(default_factory=dict)

    reply_to: str | None = None