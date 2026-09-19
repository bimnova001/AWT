from enum import Enum

from pydantic import BaseModel, Field


class DecisionType(str, Enum):

    WORK = "WORK"

    DELEGATE = "DELEGATE"

    ASK = "ASK"

    COMPLETE = "COMPLETE"

    REJECT = "REJECT"


class ProposedSubtask(BaseModel):

    description: str

    required_capabilities: list[str] = Field(
        default_factory=list
    )

    target_agent: str | None = None


class ToolCall(BaseModel):

    name: str

    arguments: dict = Field(
        default_factory=dict
    )


class AgentDecision(BaseModel):

    decision: DecisionType

    reason: str

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

    subtasks: list[ProposedSubtask] = Field(
        default_factory=list
    )

    target_agent: str | None = None

    result: str | None = None

    tool_calls: list[ToolCall] = Field(
        default_factory=list
    )