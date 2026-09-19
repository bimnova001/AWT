import asyncio

from core.protocol import AgentMessage


class MessageBus:

    def __init__(self):

        self.inboxes = {}

    def register_agent(
        self,
        agent_id: str
    ):

        if agent_id not in self.inboxes:

            self.inboxes[
                agent_id
            ] = asyncio.Queue()

    async def send(
        self,
        message: AgentMessage
    ):

        if message.to_agent is None:

            raise ValueError(
                "Message requires to_agent"
            )

        inbox = self.inboxes.get(
            message.to_agent
        )

        if inbox is None:

            raise ValueError(
                f"Unknown agent: "
                f"{message.to_agent}"
            )

        await inbox.put(
            message
        )

    async def receive(
        self,
        agent_id: str
    ):

        inbox = self.inboxes.get(
            agent_id
        )

        if inbox is None:

            raise ValueError(
                f"Unknown agent: "
                f"{agent_id}"
            )

        return await inbox.get()