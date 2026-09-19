import json
import asyncio
from typing import Any

from groq import AsyncGroq

from providers.base import ModelProvider


def make_groq_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize Pydantic JSON Schema for Groq's strict object rules."""

    normalized = json.loads(json.dumps(schema))

    def normalize(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                properties = node["properties"]
                node["additionalProperties"] = False
                node["required"] = list(properties)
            for value in node.values():
                normalize(value)
        elif isinstance(node, list):
            for value in node:
                normalize(value)

    normalize(normalized)
    return normalized


class GroqProvider(ModelProvider):

    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-oss-20b",
        name: str = "groq"
    ):
        self.api_key = api_key
        self.model = model
        self.name = name

        self.client = AsyncGroq(
            api_key=api_key
        )

    async def generate(
        self,
        messages: list[dict]
    ) -> str:

        for attempt in range(3):

            try:

                response = await self.client.chat.completions.create(

                    model=self.model,

                    messages=messages,

                )

                return (
                    response
                    .choices[0]
                    .message
                    .content
                    or ""
                )

            except Exception:

                if attempt >= 2:
                    raise

                await asyncio.sleep(
                    1.5 * (attempt + 1)
                )

    async def generate_structured(
        self,
        messages: list[dict],
        schema: dict,
        schema_name: str
    ) -> dict:

        strict_schema = make_groq_strict_schema(schema)

        for attempt in range(3):

            try:

                response = await self.client.chat.completions.create(

                    model=self.model,

                    messages=messages,

                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            "strict": True,
                            "schema": strict_schema,
                        },
                    },

                )

                content = (
                    response
                    .choices[0]
                    .message
                    .content
                )

                if not content:
                    raise RuntimeError(
                        "Groq returned empty response."
                    )

                return json.loads(content)

            except Exception:

                if attempt >= 2:
                    raise

                await asyncio.sleep(
                    1.5 * (attempt + 1)
                )

        raise RuntimeError(
            "Groq request failed."
        )