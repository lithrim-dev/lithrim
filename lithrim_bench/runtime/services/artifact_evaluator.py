"""M1 stub: structural validation + artifact judge skipped (scribe = semantic-only)."""
from __future__ import annotations

from typing import Any


async def validate_artifact_structural(*args: Any, **kwargs: Any) -> Any:
    return {"verdict": "not_applicable", "findings": [], "skipped": True}


async def _run_artifact_judge(*args: Any, **kwargs: Any) -> Any:
    raise NotImplementedError("artifact_judge skipped in M1; inject _skipped_artifact_stage")
