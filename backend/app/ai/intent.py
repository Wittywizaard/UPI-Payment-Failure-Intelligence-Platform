"""
Intent detection for the AI Assistant (PRD Section 16).

Deliberately rule-based rather than an LLM call for this step: the PRD requires
that "the LLM must NOT directly invent calculations," and keeping intent
parsing rule-based means we can guarantee which analytics function will run
before any model is involved. The LLM is used only in the final explanation
step (see orchestrator.py), strictly over the validated structured result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

# The dataset's synthetic "current time" -- one day after the last generated
# day, so that "yesterday" naturally resolves to 2026-08-29 (the day the
# injected anomaly lives on), matching the PRD's example question "Why did
# PSR drop yesterday?" (see docs/decisions.md D35).
PLATFORM_NOW = datetime(2026, 8, 30, 0, 0, 0, tzinfo=timezone.utc)

IntentType = str


@dataclass
class ParsedIntent:
    intent: IntentType
    window_start: datetime
    window_end: datetime
    window_label: str
    raw_question: str
    entities: dict = field(default_factory=dict)


def _resolve_time_window(question: str) -> tuple[datetime, datetime, str]:
    q = question.lower()

    if "yesterday" in q:
        start = (PLATFORM_NOW - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return start, end, "yesterday (2026-08-29)"

    if "today" in q:
        start = PLATFORM_NOW.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, PLATFORM_NOW, "today (2026-08-30, so far)"

    week_match = re.search(r"last (\d+) days?", q)
    if week_match:
        days = int(week_match.group(1))
        return PLATFORM_NOW - timedelta(days=days), PLATFORM_NOW, f"the last {days} days"

    if "last week" in q or "past week" in q:
        return PLATFORM_NOW - timedelta(days=7), PLATFORM_NOW, "the last 7 days"

    # Default: last 24 hours ending at the platform's synthetic "now" --
    # covers the injected anomaly window without requiring the person to
    # know the exact demo date.
    return PLATFORM_NOW - timedelta(hours=24), PLATFORM_NOW, "the last 24 hours"


def parse_intent(question: str) -> ParsedIntent:
    q = question.lower()
    start, end, label = _resolve_time_window(question)

    if any(kw in q for kw in ["why did psr drop", "why did the psr", "psr drop", "success rate drop", "why is psr"]):
        return ParsedIntent("psr_drop_reason", start, end, label, question)

    if any(kw in q for kw in ["which bank", "what bank", "bank contributed", "bank contributor"]):
        return ParsedIntent("top_bank_contributor", start, end, label, question)

    if any(kw in q for kw in ["biggest failure fingerprint", "largest fingerprint", "failure fingerprint", "top fingerprint"]):
        return ParsedIntent("top_fingerprint", start, end, label, question)

    if any(kw in q for kw in ["value at risk", "money at risk", "amount at risk", "revenue at risk"]):
        return ParsedIntent("value_at_risk", start, end, label, question)

    if any(kw in q for kw in ["intervention improve", "did the intervention", "intervention effective", "intervention work"]):
        return ParsedIntent("intervention_effectiveness", start, end, label, question)

    return ParsedIntent("general", start, end, label, question)
