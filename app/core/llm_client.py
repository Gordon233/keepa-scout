from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import settings


class LLMError(Exception):
    pass


_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.llm_base_url,
        )
    return _client


async def chat_completion(messages: list[dict], temperature: float = 0) -> str:
    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        raise LLMError(f"LLM call failed: {e}") from e


async def chat_completion_json(
    messages: list[dict],
    schema: dict,
    temperature: float = 0,
) -> dict:
    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema["title"],
                    "strict": True,
                    "schema": schema,
                },
            },
        )
        import json
        return json.loads(response.choices[0].message.content or "{}")
    except Exception as e:
        raise LLMError(f"Structured LLM call failed: {e}") from e
