import json
import asyncio
from typing import Any

from groq import AsyncGroq

from config.settings import MAX_OUTPUT_TOKENS
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

    @staticmethod
    def _is_non_retryable(error: Exception) -> bool:
        status_code = getattr(error, "status_code", None)
        return isinstance(status_code, int) and 400 <= status_code < 500

    @staticmethod
    def _is_schema_validation_error(error: Exception) -> bool:
        text = str(error).lower()
        return "json_validate_failed" in text or "does not match the expected schema" in text

    async def close(self) -> None:
        await self.client.close()

    async def generate(
        self,
        messages: list[dict]
    ) -> str:

        for attempt in range(3):

            try:

                response = await self.client.chat.completions.create(

                    model=self.model,

                    messages=messages,

                    max_tokens=MAX_OUTPUT_TOKENS,

                )

                return (
                    response
                    .choices[0]
                    .message
                    .content
                    or ""
                )

            except Exception as error:

                if self._is_non_retryable(error):
                    raise

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

                    max_tokens=MAX_OUTPUT_TOKENS,

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

            except Exception as error:

                if self._is_schema_validation_error(error) and attempt == 0:
                    messages = [*messages, {
                        "role": "user",
                        "content": (
                            "Schema correction: return valid JSON with every required "
                            "property present. Do not omit any field."
                        ),
                    }]
                    continue

                if self._is_non_retryable(error):
                    raise

                if attempt >= 2:
                    raise

                await asyncio.sleep(
                    1.5 * (attempt + 1)
                )

        raise RuntimeError(
            "Groq request failed."
        )