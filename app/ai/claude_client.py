# app/ai/claude_client.py
# Thin wrapper around the Anthropic SDK plus a helper for calling Claude with
# a Pydantic model as the required structured output (output_config.format).

import json
from typing import TypeVar

from anthropic import Anthropic
from pydantic import BaseModel

from app.config import ANTHROPIC_API_KEY

MODEL = "claude-opus-4-8"

_client: Anthropic | None = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


T = TypeVar("T", bound=BaseModel)


def generate_structured(*, system: str, user: str, schema_model: type[T], max_tokens: int = 4096, stream: bool = False) -> T:
    """Call Claude with a strict JSON schema and return a validated Pydantic instance.

    Pass stream=True for large max_tokens calls — the SDK refuses a non-streaming
    request outright once the requested max_tokens implies a generation that could
    run past its 10-minute non-streaming cap."""
    client = get_client()
    schema = schema_model.model_json_schema()
    kwargs = dict(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": schema,
            }
        },
    )

    if stream:
        with client.messages.stream(**kwargs) as s:
            response = s.get_final_message()
    else:
        response = client.messages.create(**kwargs)

    text_block = next((b for b in response.content if b.type == "text"), None)
    if text_block is None:
        raise ValueError(f"No text content in Claude response (stop_reason={response.stop_reason})")

    data = json.loads(text_block.text)
    return schema_model.model_validate(data)


def generate_text(*, system: str, user: str, max_tokens: int = 1024) -> str:
    client = get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text_block = next((b for b in response.content if b.type == "text"), None)
    return text_block.text if text_block else ""
