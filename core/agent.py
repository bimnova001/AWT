import json

from core.decision import (
    AgentDecision,
    DecisionType
)
from tools.system import ToolRequest

from core.protocol import (
    AgentMessage,
    MessageType
)

from core.task import (
    Task,
    TaskStatus
)
from config.settings import MAX_CONTEXT_CHARS, MAX_RESULT_CHARS
from core.text_style import event, style
from core.error_style import public_error_message


def clip_text(value: object, limit: int) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    head = max(1, limit * 2 // 3)
    tail = limit - head
    return f"{text[:head]}\n...[truncated {len(text) - limit} chars]...\n{text[-tail:]}"


class Agent:

    def __init__(
        self,
        agent_id,
        provider,
        capabilities,
        bus,
        network,
        orchestrator
    ):

        self.agent_id = agent_id

        self.provider = provider

        self.capabilities = capabilities

        self.bus = bus

        self.network = network

        self.orchestrator = orchestrator

        self.running = False

    def info(self):

        return {

            "agent_id":
                self.agent_id,

            "capabilities":
                self.capabilities,

        }

    async def send(
        self,
        message
    ):

        await self.bus.send(
            message
        )

    async def decide(
        self,
        task: Task,
        context: str = ""
    ) -> AgentDecision:

        other_agents = [

            agent

            for agent in self.network.describe()

            if agent["agent_id"]
            != self.agent_id

        ]

        prompt = f"""
You are an autonomous AI agent inside
a dynamic multi-agent collaboration system.

You do NOT have a fixed role.

Your capabilities:
{json.dumps(self.capabilities, indent=2)}

Other available agents:
{json.dumps(other_agents, indent=2)}

Current task:
{clip_text(task.model_dump_json(indent=2), MAX_CONTEXT_CHARS // 2)}

Context:
{clip_text(context, MAX_CONTEXT_CHARS)}

Available system tools:
{json.dumps(self.orchestrator.tool_registry.describe() if self.orchestrator.tool_registry else [], indent=2)}

Your job is to decide what should happen next.

Available decisions:

WORK
- You can solve the task yourself.
- Do NOT create subtasks unless necessary.

DELEGATE
- The task is better divided into smaller tasks.
- Create one or more subtasks.
- Choose agents based on capabilities.
- Do not delegate everything automatically.

ASK
- You need information from another agent.

COMPLETE
- The task is already solved.
- Return the result.

REJECT
- You cannot reasonably contribute.

Important:

1. Never assume an agent has a capability it does not list.
2. Prefer solving tasks yourself when you are capable.
3. Delegate only meaningful independent work.
4. Avoid duplicate work.
5. Do not create unnecessary subtasks.
6. If working on a subtask, produce a useful concrete result.
7. If a task requires multiple disciplines, decomposition is encouraged.
8. You are not a manager. You are an autonomous collaborator.
9. Propose tool_calls only when necessary. The orchestrator validates every
    call, and the user must approve write_file and run_shell.
11. Put tool arguments in the arguments field as a JSON object encoded as a
    string, for example: '{{"path":"README.md"}}'.

Return only the requested structured decision.
"""

        result = await self.provider.generate_structured(

            messages=[

                {
                    "role": "system",
                    "content":
                        "You are an autonomous "
                        "multi-agent worker."
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ],

            schema=
                AgentDecision.model_json_schema(),

            schema_name=
                "agent_decision"

        )

        return AgentDecision.model_validate(
            result
        )

    async def execute(
        self,
        task: Task
    ):

        task.status = TaskStatus.RUNNING

        task.attempts += 1

        context = self.build_context(
            task
        )

        decision = await self.decide(
            task,
            context
        )

        print()
        print(event(
            self.agent_id,
            f"{task.task_id[:8]} => {decision.decision.value}",
        ))

        print(
            style(f"Reason: {decision.reason}", "blue")
        )

        tool_context = await self.run_tool_calls(task, decision)
        if tool_context:
            context = f"{context}\n\nTool results:\n{tool_context}"

        if decision.decision == DecisionType.WORK:

            result = await self.work(
                task,
                context
            )

            await self.orchestrator.submit_result(
                task,
                self,
                result
            )

            return

        if decision.decision == DecisionType.COMPLETE:

            await self.orchestrator.submit_result(

                task,

                self,

                decision.result
                or "Task completed."

            )

            return

        if decision.decision == DecisionType.DELEGATE:

            await self.orchestrator.handle_delegation(

                task,

                self,

                decision

            )

            return

        if decision.decision == DecisionType.ASK:

            await self.orchestrator.handle_question(

                task,

                self,

                decision

            )

            return

        if decision.decision == DecisionType.REJECT:

            await self.orchestrator.handle_rejection(

                task,

                self,

                decision

            )

            return

    async def run_tool_calls(
        self,
        task: Task,
        decision: AgentDecision
    ) -> str:

        results = []

        for call in decision.tool_calls:
            try:
                arguments = json.loads(call.arguments)
            except json.JSONDecodeError:
                arguments = {}
            result = await self.orchestrator.execute_tool(
                ToolRequest(
                    name=call.name,
                    arguments=arguments,
                    agent_id=self.agent_id,
                    task_id=task.task_id,
                )
            )
            status = "approved" if result.approved else "denied"
            details = result.output or result.error or "No output"
            results.append(
                f"{call.name} ({status}):\n"
                f"{clip_text(details, MAX_RESULT_CHARS // 2)}"
            )

        return "\n\n".join(results)

    async def work(
        self,
        task: Task,
        context: str
    ):

        prompt = f"""
You are working on this task:

{task.description}

Your capabilities:
{json.dumps(self.capabilities)}

Previous context:
{clip_text(context, MAX_CONTEXT_CHARS)}

Perform the task as far as possible.

Tool execution is disabled during this response. Do not call tools,
do not emit tool-call JSON/XML, and do not use tool names from another
system such as repo_browser.open_file. Use only the tool results included
in the context and return plain-text engineering output.

If external information or tools are unavailable,
state the limitation clearly.

Return a useful engineering result containing:

- what you determined
- implementation/reasoning
- important details
- limitations
- next steps if needed

For reviews, distinguish verified findings from assumptions. Do not infer
file contents, frameworks, endpoints, or model usage from filenames alone.
If a file was not actually read, say that it was not verified.
"""

        return await self.provider.generate(

            messages=[

                {
                    "role": "system",
                    "content":
                        "You are a productive engineering agent. "
                        "Return plain text only. Tool calls are disabled "
                        "in this work response."
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ]

        )

    def build_context(
        self,
        task: Task
    ):

        parent = None

        if task.parent_task_id:

            parent = self.orchestrator.graph.get(
                task.parent_task_id
            )

        parts = []

        if parent:

            parts.append(
                f"Parent task:\n"
                f"{parent.description}"
            )

            if parent.result:

                parts.append(
                    f"Parent result:\n"
                    f"{clip_text(parent.result, MAX_RESULT_CHARS)}"
                )

        if task.result:

            parts.append(
                f"Previous result:\n"
                f"{clip_text(task.result, MAX_RESULT_CHARS)}"
            )

        return "\n\n".join(
            parts
        )

    async def handle_message(
        self,
        message: AgentMessage
    ):

        print()

        print(
            f"[{self.agent_id}] "
            f"received "
            f"{message.type.value} "
            f"from "
            f"{message.from_agent}"
        )

        if message.type == MessageType.TASK_OFFER:

            task = self.orchestrator.graph.get(
                message.task_id
            )

            if task:

                await self.execute(
                    task
                )

        elif message.type == MessageType.REVIEW_REQUEST:

            task = self.orchestrator.graph.get(
                message.task_id
            )

            if task:

                await self.review(
                    task
                )

    async def review(
        self,
        task: Task
    ):

        result = task.result or ""

        prompt = f"""
You are reviewing work produced by another AI agent.

Task:
{clip_text(task.description, MAX_CONTEXT_CHARS // 2)}

Agent:
{task.assigned_agent}

Result:
{clip_text(result, MAX_RESULT_CHARS)}

Your capabilities:
{json.dumps(self.capabilities)}

Evaluate the result.

Check:

1. correctness
2. completeness
3. technical quality
4. whether the result actually addresses the task
5. obvious errors or missing requirements

Return a structured review.
"""

        review = await self.provider.generate_structured(

            messages=[

                {
                    "role": "system",
                    "content":
                        "You are an independent reviewer."
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ],

            schema={

                "type": "object",

                "properties": {

                    "approved": {
                        "type": "boolean"
                    },

                    "score": {
                        "type": "number"
                    },

                    "feedback": {
                        "type": "string"
                    },

                    "required_changes": {

                        "type": "array",

                        "items": {
                            "type": "string"
                        }

                    }

                },

                "required": [

                    "approved",
                    "score",
                    "feedback",
                    "required_changes"

                ],

                "additionalProperties": False

            },

            schema_name="task_review"

        )

        await self.orchestrator.submit_review(

            task,

            self,

            review

        )

    async def run(self):

        self.running = True

        while self.running:

            message = await self.bus.receive(
                self.agent_id
            )

            try:

                await self.handle_message(
                    message
                )

            except Exception as e:

                print(event(
                    self.agent_id,
                    public_error_message(e),
                    "red",
                ))

                if message.task_id:
                    failed_task = self.orchestrator.graph.get(
                        message.task_id
                    )
                    if failed_task:
                        await self.orchestrator.fail_task(
                            failed_task,
                            str(e),
                        )

    def stop(self):

        self.running = False