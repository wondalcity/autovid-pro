"""Shared LLM client — uses Anthropic Claude by default, falls back to OpenAI.

Priority:
  1. ANTHROPIC_API_KEY → claude-haiku-4-5 (fast, cheap)
  2. OPENAI_API_KEY    → gpt-4o-mini
"""
import json
import logging
from typing import Any

from app.utils.settings_store import get as _cfg

logger = logging.getLogger(__name__)

# Model names
_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
_OPENAI_MODEL = "gpt-4o-mini"


def _recover_truncated_json(raw: str) -> dict:
    """Attempt to parse a truncated JSON string by trimming to last valid complete object."""
    # For arrays: find last complete }, then close the array
    if '"scenes"' in raw or raw.lstrip().startswith("[") or '"scenes"' in raw[:50]:
        # Try to close the array at the last complete item
        last_close = raw.rfind("},")
        if last_close == -1:
            last_close = raw.rfind("}")
        if last_close > 0:
            trimmed = raw[:last_close + 1]
            # Find the opening brace of the outer object
            bracket_start = raw.find("[")
            if bracket_start > 0:
                key_start = raw.rfind('"', 0, bracket_start)
                outer = raw[:bracket_start] + trimmed[bracket_start:] + "]}"
                try:
                    return json.loads(outer)
                except Exception:
                    pass
            try:
                return json.loads(trimmed + "]}")
            except Exception:
                pass
    # Fallback: try to extract a partial array
    try:
        start = raw.find("[")
        if start >= 0:
            last = raw.rfind("}")
            candidate = raw[start:last + 1] + "]"
            items = json.loads(candidate)
            return {"scenes": items if isinstance(items, list) else []}
    except Exception:
        pass
    return {}


async def chat_json(
    system: str,
    user: str,
    temperature: float = 0.4,
    max_tokens: int = 4096,
) -> dict:
    """Send a chat request and return parsed JSON dict.

    Tries Anthropic first, then OpenAI.  Raises on total failure.
    """
    if _cfg("ANTHROPIC_API_KEY"):
        return await _anthropic_json(system, user, temperature, max_tokens)
    if _cfg("OPENAI_API_KEY"):
        return await _openai_json(system, user, temperature, max_tokens)
    raise RuntimeError(
        "AI API key not configured. "
        "Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env or Settings"
    )


async def chat_text(
    system: str,
    user: str,
    temperature: float = 0.5,
    max_tokens: int = 8192,
) -> str:
    """Send a chat request and return plain text response."""
    if _cfg("ANTHROPIC_API_KEY"):
        return await _anthropic_text(system, user, temperature, max_tokens)
    if _cfg("OPENAI_API_KEY"):
        return await _openai_text(system, user, temperature, max_tokens)
    raise RuntimeError(
        "AI API key not configured. "
        "Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env or Settings"
    )


# ─── Anthropic backend ────────────────────────────────────────────────────────

async def _anthropic_json(system: str, user: str, temperature: float, max_tokens: int) -> dict:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=_cfg("ANTHROPIC_API_KEY"))
    msg = await client.messages.create(
        model=_ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system + "\n\nIMPORTANT: Return ONLY valid JSON. No markdown fences, no extra text.",
        messages=[{"role": "user", "content": user}],
    )
    raw = msg.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Attempt to recover truncated JSON by finding the last complete item
        logger.warning("[llm] JSON truncated — attempting partial recovery")
        return _recover_truncated_json(raw)


async def _anthropic_text(system: str, user: str, temperature: float, max_tokens: int) -> str:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=_cfg("ANTHROPIC_API_KEY"))
    msg = await client.messages.create(
        model=_ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text.strip()


# ─── OpenAI backend ───────────────────────────────────────────────────────────

async def _openai_json(system: str, user: str, temperature: float, max_tokens: int) -> dict:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=_cfg("OPENAI_API_KEY"))
    resp = await client.chat.completions.create(
        model=_OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return json.loads(resp.choices[0].message.content)


async def _openai_text(system: str, user: str, temperature: float, max_tokens: int) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=_cfg("OPENAI_API_KEY"))
    resp = await client.chat.completions.create(
        model=_OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()
