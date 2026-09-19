from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DecisionType(str, Enum):

    WORK = "WORK"

    DELEGATE = "DELEGATE"

    ASK = "ASK"

    COMPLETE = "COMPLETE"

    REJECT = "REJECT"


class ProposedSubtask(BaseModel):

    model_config = ConfigDict(extra="forbid")

    description: str

    role: str = Field(
        default="generalist",
        description="Temporary role for this subtask, chosen from its requirements.",
    )

    required_capabilities: list[str] = Field(
        default_factory=list
    )

    target_agent: str | None = None


class ToolCall(BaseModel):

    model_config = ConfigDict(extra="forbid")

    name: str

    arguments: str = "{}"


class AgentDecision(BaseModel):

    model_config = ConfigDict(extra="forbid")

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
