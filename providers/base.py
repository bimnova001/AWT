from abc import ABC, abstractmethod


class ModelProvider(ABC):

    @abstractmethod
    async def generate(
        self,
        messages: list[dict]
    ) -> str:
        pass

    @abstractmethod
    async def generate_structured(
        self,
        messages: list[dict],
        schema: dict,
        schema_name: str
    ) -> dict:
        pass