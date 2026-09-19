import asyncio
from uuid import uuid4

from core.protocol import (
    AgentMessage,
    MessageType
)

from core.task import (
    Task,
    TaskStatus
)

from core.task_graph import TaskGraph
from tools.system import ApprovalHandler, ToolRegistry, ToolRequest, ToolResult


class Orchestrator:

    def __init__(
        self,
        bus,
        network,
        max_tasks=30,
        max_depth=4,
        max_review_rounds=2,
        tool_registry=None,
        approval_handler=None,
    ):

        self.bus = bus

        self.network = network

        self.graph = TaskGraph()

        self.max_tasks = max_tasks

        self.max_depth = max_depth

        self.max_review_rounds = (
            max_review_rounds
        )

        self.root_task = None

        self.completed = False

        self.tool_registry: ToolRegistry | None = tool_registry
        self.approval_handler: ApprovalHandler = approval_handler or (
            lambda request: False
        )

    async def execute_tool(self, request: ToolRequest) -> ToolResult:
        if self.tool_registry is None:
            return ToolResult(request.name, False, "", "Tools are not configured.")

        try:
            requires_approval = self.tool_registry.requires_approval(request.name)
        except ValueError as error:
            return ToolResult(request.name, False, "", str(error))

        if requires_approval and not self.approval_handler(request):
            return ToolResult(request.name, False, "", "User denied tool action.")

        result = self.tool_registry.execute(request)
        status = "ok" if not result.error else result.error
        print(f"[TOOL] {request.agent_id} -> {request.name}: {status}")
        return result

    # ------------------------------------------------
    # TASK CREATION
    # ------------------------------------------------

    def create_root_task(
        self,
        description: str
    ):

        task = Task(

            description=description,

            created_by="USER",

            status=TaskStatus.PROPOSED,

        )

        self.graph.add(task)

        self.root_task = task

        return task

    # ------------------------------------------------
    # START
    # ------------------------------------------------

    async def start(self, task: Task):
        print()
        print("=" * 70)
        print("ROOT TASK")
        print()
        print(task.description)

        print()
        print("=" * 70)

        # Initial agent only.
        # This agent decides whether to work,
        # decompose, delegate, or reject.

        agents = self.network.all_agents()

        if not agents:
            await self.fail_task(
                task,
                "No agents available."
            )
            return

        starter = agents[0]

        await self.offer_task(
            task,
            starter.agent_id
        )

    # ------------------------------------------------
    # OFFER
    # ------------------------------------------------

    async def offer_task(
        self,
        task: Task,
        agent_id: str
    ):

        if task.status in {

            TaskStatus.COMPLETED,

            TaskStatus.CANCELLED

        }:

            return

        message = AgentMessage(

            message_id=str(uuid4()),

            from_agent="ORCHESTRATOR",

            to_agent=agent_id,

            type=MessageType.TASK_OFFER,

            task_id=task.task_id,

            payload={

                "description":
                    task.description,

                "required_capabilities":
                    task.required_capabilities,

            }

        )

        await self.bus.send(
            message
        )

    # ------------------------------------------------
    # DELEGATION
    # ------------------------------------------------

    async def handle_delegation(
        self,
        parent: Task,
        agent,
        decision
    ):

        if self.graph.count() >= self.max_tasks:

            await self.fail_task(

                parent,

                "Maximum task limit reached."

            )

            return

        depth = self.get_depth(
            parent
        )

        if depth >= self.max_depth:

            # At max depth we force the agent
            # to work instead of spawning more.

            result = await agent.work(
                parent,
                agent.build_context(parent)
            )

            await self.submit_result(
                parent,
                agent,
                result
            )

            return

        print()

        print(
            f"[ORCHESTRATOR] "
            f"{agent.agent_id} "
            f"decomposed "
            f"{parent.task_id[:8]}"
        )

        if not decision.subtasks:

            # Agent said delegate but gave
            # no subtasks -> fallback to work.

            result = await agent.work(
                parent,
                agent.build_context(parent)
            )

            await self.submit_result(
                parent,
                agent,
                result
            )

            return

        parent.status = TaskStatus.RUNNING

        created = []

        for proposal in decision.subtasks:

            if self.graph.count() >= self.max_tasks:

                break

            target = proposal.target_agent

            # Validate requested target

            if target:

                target_agent = (
                    self.network.get_agent(
                        target
                    )
                )

                if target_agent is None:

                    target = None

            # If no target was selected,
            # find agents with matching capabilities.

            if not target:

                candidates = (
                    self.network.find_capable(
                        proposal.required_capabilities
                    )
                )

                # Never assign back to creator
                # unless nobody else can do it.

                candidates = [

                    x for x in candidates

                    if x.agent_id
                    != agent.agent_id

                ] or candidates

                if candidates:

                    target = candidates[0].agent_id

            if not target:

                continue

            child = self.graph.create_subtask(

                parent=parent,

                description=
                    proposal.description,

                capabilities=
                    proposal.required_capabilities,

                created_by=
                    agent.agent_id,

                target_agent=
                    target

            )

            created.append(
                child
            )

            print(

                f"  ├─ {child.task_id[:8]} "
                f"→ {target}"

            )

            await self.offer_task(
                child,
                target
            )

        if not created:

            result = await agent.work(

                parent,

                agent.build_context(parent)

            )

            await self.submit_result(
                parent,
                agent,
                result
            )

    # ------------------------------------------------
    # RESULT
    # ------------------------------------------------

    async def submit_result(
        self,
        task: Task,
        agent,
        result
    ):

        task.result = result

        task.status = TaskStatus.REVIEW

        task.assigned_agent = (
            agent.agent_id
        )

        print()

        print(
            f"[ORCHESTRATOR] "
            f"RESULT from "
            f"{agent.agent_id} "
            f"for "
            f"{task.task_id[:8]}"
        )

        reviewer = self.choose_reviewer(
            task,
            agent
        )

        if reviewer:

            task.reviewer_agent = (
                reviewer.agent_id
            )

            await self.bus.send(

                AgentMessage(

                    message_id=str(uuid4()),

                    from_agent="ORCHESTRATOR",

                    to_agent=
                        reviewer.agent_id,

                    type=
                        MessageType.REVIEW_REQUEST,

                    task_id=
                        task.task_id,

                    payload={

                        "result":
                            result

                    }

                )

            )

        else:

            await self.complete_task(
                task
            )

    # ------------------------------------------------
    # REVIEW
    # ------------------------------------------------

    def choose_reviewer(
        self,
        task,
        worker
    ):

        candidates = [

            agent

            for agent
            in self.network.all_agents()

            if agent.agent_id
            != worker.agent_id

        ]

        if not candidates:

            return None

        # Prefer agents that overlap with
        # required capabilities.

        required = set(
            task.required_capabilities
        )

        scored = []

        for agent in candidates:

            overlap = len(
                required
                & set(agent.capabilities)
            )

            scored.append(
                (
                    overlap,
                    agent
                )
            )

        scored.sort(
            key=lambda x: x[0],
            reverse=True
        )

        return scored[0][1]

    async def submit_review(
        self,
        task,
        reviewer,
        review
    ):

        task.review_result = review

        print()

        print(
            f"[REVIEW] "
            f"{reviewer.agent_id} "
            f"→ "
            f"{task.task_id[:8]}"
        )

        print(
            f"Approved: "
            f"{review['approved']}"
        )

        print(
            f"Score: "
            f"{review['score']}"
        )

        print(
            f"Feedback: "
            f"{review['feedback']}"
        )

        if review["approved"]:

            await self.complete_task(
                task
            )

            return

        # -------------------------
        # REWORK
        # -------------------------

        task.review_round += 1

        if (
            task.review_round
            > self.max_review_rounds
        ):

            await self.fail_task(

                task,

                "Maximum review rounds exceeded."

            )

            return

        task.status = TaskStatus.REWORK

        worker = self.network.get_agent(
            task.assigned_agent
        )

        if not worker:

            await self.fail_task(

                task,

                "Original worker unavailable."

            )

            return

        print()

        print(
            f"[REWORK] "
            f"{task.task_id[:8]} "
            f"→ "
            f"{worker.agent_id}"
        )

        task.metadata[
            "review_feedback"
        ] = review["feedback"]

        task.metadata[
            "required_changes"
        ] = review["required_changes"]

        task.status = TaskStatus.PROPOSED

        await self.offer_task(
            task,
            worker.agent_id
        )

    # ------------------------------------------------
    # COMPLETION
    # ------------------------------------------------

    async def complete_task(
        self,
        task
    ):

        task.status = TaskStatus.COMPLETED

        print()

        print(
            f"[COMPLETE] "
            f"{task.task_id[:8]}"
        )

        # Check parent

        if task.parent_task_id:

            parent = self.graph.get(
                task.parent_task_id
            )

            if parent:

                await self.check_parent(
                    parent
                )

        else:

            self.completed = True

            print()

            print(
                "=" * 70
            )

            print(
                "ROOT TASK COMPLETED"
            )

            print(
                "=" * 70
            )

    async def check_parent(
        self,
        parent
    ):

        if not self.graph.all_children_completed(
            parent
        ):

            return

        print()

        print(
            f"[ORCHESTRATOR] "
            f"All children completed "
            f"for {parent.task_id[:8]}"
        )

        # Synthesize child results.

        results = []

        for child in self.graph.children(
            parent
        ):

            results.append(

                f"""
TASK:
{child.description}

AGENT:
{child.assigned_agent}

RESULT:
{child.result}
"""

            )

        # Give the parent back to an agent
        # for synthesis.

        candidates = self.network.all_agents()

        if not candidates:

            await self.complete_task(
                parent
            )

            return

        synthesizer = candidates[0]

        parent.metadata[
            "child_results"
        ] = results

        parent.status = TaskStatus.PROPOSED

        parent.description = (

            parent.description

            + "\n\nSynthesize the following "
              "completed subtasks:\n"

            + "\n".join(results)

        )

        await self.offer_task(

            parent,

            synthesizer.agent_id

        )

    # ------------------------------------------------
    # QUESTIONS
    # ------------------------------------------------

    async def handle_question(
        self,
        task,
        agent,
        decision
    ):

        target = decision.target_agent

        if target:

            target_agent = (
                self.network.get_agent(
                    target
                )
            )

        else:

            target_agent = None

        if target_agent is None:

            candidates = (
                self.network.all_agents()
            )

            candidates = [

                x for x in candidates

                if x.agent_id
                != agent.agent_id

            ]

            target_agent = (
                candidates[0]
                if candidates
                else None
            )

        if not target_agent:

            return

        await self.bus.send(

            AgentMessage(

                message_id=str(uuid4()),

                from_agent=
                    agent.agent_id,

                to_agent=
                    target_agent.agent_id,

                type=
                    MessageType.QUESTION,

                task_id=
                    task.task_id,

                payload={

                    "question":
                        decision.reason

                }

            )

        )

    # ------------------------------------------------
    # REJECTION
    # ------------------------------------------------

    async def handle_rejection(
        self,
        task,
        agent,
        decision
    ):

        print()

        print(
            f"[REJECT] "
            f"{agent.agent_id} "
            f"rejected "
            f"{task.task_id[:8]}"
        )

        candidates = [

            x

            for x
            in self.network.all_agents()

            if x.agent_id
            != agent.agent_id

        ]

        if not candidates:

            await self.fail_task(
                task,
                decision.reason
            )

            return

        # Try another agent

        task.status = TaskStatus.PROPOSED

        await self.offer_task(

            task,

            candidates[0].agent_id

        )

    # ------------------------------------------------
    # FAIL
    # ------------------------------------------------

    async def fail_task(
        self,
        task,
        reason
    ):

        task.status = TaskStatus.FAILED

        task.metadata[
            "failure_reason"
        ] = reason

        print()

        print(
            f"[FAILED] "
            f"{task.task_id[:8]}"
        )

        print(
            reason
        )

    # ------------------------------------------------
    # DEPTH
    # ------------------------------------------------

    def get_depth(
        self,
        task
    ):

        depth = 0

        current = task

        while current.parent_task_id:

            depth += 1

            current = self.graph.get(
                current.parent_task_id
            )

            if not current:
                break

        return depth

    # ------------------------------------------------
    # STATUS
    # ------------------------------------------------

    def print_tree(
        self,
        task=None,
        level=0
    ):

        if task is None:

            task = self.root_task

        if not task:
            return

        prefix = "    " * level

        print(

            f"{prefix}"
            f"├─ "
            f"{task.task_id[:8]} "
            f"[{task.status.value}] "
            f"{task.description[:80]}"

        )

        for child in self.graph.children(
            task
        ):

            self.print_tree(
                child,
                level + 1
            )