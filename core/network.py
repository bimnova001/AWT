class AgentNetwork:

    def __init__(self):

        self.agents = {}

    def register(self, agent):

        self.agents[
            agent.agent_id
        ] = agent

    def get_agent(self, agent_id):

        return self.agents.get(
            agent_id
        )

    def all_agents(self):

        return list(
            self.agents.values()
        )

    def describe(self):

        return [

            {
                "agent_id": agent.agent_id,
                "capabilities": agent.capabilities,
            }

            for agent in self.agents.values()

        ]

    def find_capable(
        self,
        capabilities: list[str]
    ):

        if not capabilities:
            return self.all_agents()

        required = set(
            capabilities
        )

        result = []

        for agent in self.agents.values():

            available = set(
                agent.capabilities
            )

            if required.issubset(
                available
            ):
                result.append(agent)

        return result