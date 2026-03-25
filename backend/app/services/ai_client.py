import json
import re
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def estimate_tokens(text: str) -> int:
    # Rough approximation to avoid large over-budget requests.
    return max(1, len(text) // 4)


def parse_json_content(content: str) -> dict[str, Any]:
    body = content.strip()
    if body.startswith("{") and body.endswith("}"):
        return json.loads(body)

    match = JSON_BLOCK_RE.search(body)
    if match:
        return json.loads(match.group(1))

    left = body.find("{")
    right = body.rfind("}")
    if left >= 0 and right > left:
        return json.loads(body[left : right + 1])

    raise ValueError("No JSON object found")


def resolve_chat_completions_endpoint(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/chat/completions"):
        return trimmed
    if trimmed.endswith("/v1"):
        return f"{trimmed}/chat/completions"
    return f"{trimmed}/v1/chat/completions"


def enforce_turn_budget(messages: list[dict], output_max_tokens: int) -> None:
    merged = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
    estimated_input = estimate_tokens(merged)
    estimated_total = estimated_input + output_max_tokens
    if estimated_total > settings.turn_token_budget:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Estimated tokens {estimated_total} exceed budget {settings.turn_token_budget}. "
                "Please shorten the input or reduce history."
            ),
        )


async def call_openai_chat(messages: list[dict], max_tokens: int) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured")

    endpoint = resolve_chat_completions_endpoint(settings.openai_base_url)
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    base_payload = {
        "model": settings.openai_model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            endpoint,
            headers=headers,
            json={**base_payload, "response_format": {"type": "json_object"}},
        )
        if response.status_code == 400:
            # Some OpenAI-compatible providers do not support response_format.
            response = await client.post(endpoint, headers=headers, json=base_payload)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"AI provider request failed: {response.status_code} {response.text[:400]}",
        )

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise HTTPException(status_code=502, detail="Unexpected AI provider response shape")

    try:
        return parse_json_content(content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"AI output JSON parse failed: {exc}")
