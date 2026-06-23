"""M1 stub: retrieval disabled (grounding empty). Real local-vector retrieval is post-M1."""
from __future__ import annotations

from typing import Any


async def retrieve_for_request(request: Any) -> dict[str, Any]:
    return {"matches": [], "stats": {"namespaces": [], "disabled": True}}
