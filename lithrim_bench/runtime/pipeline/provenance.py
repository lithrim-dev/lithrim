"""M1 stub: no-op provenance (no Mongo). Swap to a SQLite store later."""
from __future__ import annotations
from typing import Any, Optional


class ProvenanceStore:
    async def save(self, provenance: Any, *, agent_id: Optional[str] = None) -> None:
        return None


class NoOpProvenanceStore(ProvenanceStore):
    async def save(self, provenance: Any, *, agent_id: Optional[str] = None) -> None:
        return None


MongoProvenanceStore = NoOpProvenanceStore
