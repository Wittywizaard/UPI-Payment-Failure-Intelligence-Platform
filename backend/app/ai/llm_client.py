"""
Thin wrapper around the Anthropic API. Used ONLY to turn an already-validated
structured result into natural language -- never to compute or invent a
number. If no API key is configured, callers fall back to deterministic
template summaries so the feature works out of the box without requiring the
person to supply their own key (see docs/decisions.md D36).
"""

from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger("upi_fip.ai")
settings = get_settings()

_client = None
_client_init_attempted = False


def _get_client():
    global _client, _client_init_attempted
    if _client_init_attempted:
        return _client
    _client_init_attempted = True

    if not settings.ANTHROPIC_API_KEY:
        return None

    try:
        import anthropic
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to initialize Anthropic client")
        _client = None
    return _client


def is_llm_available() -> bool:
    return _get_client() is not None


def explain_with_llm(system_prompt: str, user_prompt: str) -> str | None:
    """
    Returns the LLM's explanation text, or None if the LLM is unavailable or
    the call fails for any reason (network, auth, rate limit) -- callers must
    have a non-LLM fallback ready.
    """
    client = _get_client()
    if client is None:
        return None

    try:
        response = client.messages.create(
            model=settings.AI_MODEL,
            max_tokens=400,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text_blocks = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        return "\n".join(text_blocks).strip() or None
    except Exception:  # noqa: BLE001
        logger.exception("LLM explanation call failed; falling back to template")
        return None
