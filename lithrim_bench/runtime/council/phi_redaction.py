"""PHI redaction utilities for external LLM usage."""

from __future__ import annotations

import re
from typing import Iterable, Sequence, Tuple

from .settings import settings


PHI_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("phone", re.compile(r"\b\+?1?\s*\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    (
        "dob",
        re.compile(
            r"\b(?:dob|date of birth|born on)\b[:\s]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
            re.IGNORECASE,
        ),
    ),
    (
        "mrn",
        re.compile(
            r"\b(?:mrn|medical record number|patient id|patient identifier)"
            r"\s*[:#]?\s*[A-Za-z0-9\-]{4,}\b",
            re.IGNORECASE,
        ),
    ),
    (
        "address",
        re.compile(
            r"\b\d{1,5}\s+[A-Za-z0-9.\- ]+\s+(?:Street|St|Avenue|Ave|Road|Rd|"
            r"Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Place|Pl)\b",
            re.IGNORECASE,
        ),
    ),
)


def _normalize_provider(provider: str) -> str:
    return provider.strip().lower()


def _eligible_providers() -> set[str]:
    return {provider.lower() for provider in settings.HIPAA_ELIGIBLE_LLM_PROVIDERS}


def _enforce_provider_policy(provider: str) -> None:
    if not settings.HIPAA_REQUIRE_ELIGIBLE_LLM_PROVIDER:
        return
    normalized = _normalize_provider(provider)
    if normalized not in _eligible_providers():
        raise ValueError(
            f"Provider '{provider}' is not HIPAA-eligible under current settings."
        )


def redact_text(text: str) -> str:
    """Redact PHI patterns from text."""
    if not text:
        return text
    redacted = text
    for label, pattern in PHI_PATTERNS:
        redacted = pattern.sub(f"[REDACTED_{label.upper()}]", redacted)
    return redacted


def sanitize_prompt(prompt: str, provider: str) -> str:
    """Enforce HIPAA provider policy and redact PHI in prompt text."""
    _enforce_provider_policy(provider)
    if settings.HIPAA_REQUIRE_PHI_REDACTION:
        return redact_text(prompt)
    return prompt


def sanitize_messages(messages: Sequence[object], provider: str) -> Sequence[object]:
    """Enforce HIPAA provider policy and redact PHI in message content."""
    _enforce_provider_policy(provider)
    if not settings.HIPAA_REQUIRE_PHI_REDACTION:
        return messages

    for message in messages:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            setattr(message, "content", redact_text(content))
    return messages


def sanitize_payloads(payloads: Iterable[str], provider: str) -> list[str]:
    """Redact PHI for multiple payloads using the same provider policy."""
    _enforce_provider_policy(provider)
    if not settings.HIPAA_REQUIRE_PHI_REDACTION:
        return list(payloads)
    return [redact_text(payload) for payload in payloads]
