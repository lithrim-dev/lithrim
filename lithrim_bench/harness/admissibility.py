"""Domain-agnostic taxonomy-snapshot admissibility helpers (the S-BS-10/12 gradeable gate).

PACK-DIST-2 (C3): these two helpers were authored on ``scripts/seed_ontology.py`` (the
clinical ontology BUILDER), but they are **generic** — they operate on a taxonomy snapshot
(the contract-of-record) and a flag list, with no clinical content. The live BFF config-write
gate (``apps/bff/app.py`` ``_validate_ontology`` → PUT ``/v1/ontology``) imported them from
``seed_ontology`` at module load, which kept the clinical builder physically in the CE
``scripts/`` tree after PACK-DIST-1 moved the rest of the clinical realm out. This module
holds the generic core so the builder can relocate into the pack repo, leaving the live
admissibility path clinical-free.

The snapshot is resolved via the **active pack** (``harness.pack``), never a hardcoded
clinical path — :func:`active_snapshot_codes` is the single snapshot-resolution path the BFF
uses (it replaces the former app-local ``_active_snapshot_codes``). :func:`load_snapshot_codes`
is the file-path form for callers that already hold a snapshot path (e.g. the relocated
``seed_ontology`` lint, which builds before any pack is active).

stdlib + ``harness.pack`` only (no ``openai``/``dspy``) — import-safe on the BFF startup path.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_snapshot_codes(path: str | Path) -> set[str]:
    """The tier union from a ``taxonomy_snapshot.json`` file — the gradeable gate.

    The snapshot is the CLAUDE.md contract-of-record; its ``tiers`` union (tier_1 +
    tier_2 + tier_3) is the authoritative set of codes the harness may score. Use this
    when you already hold a snapshot PATH (e.g. the seed-build lint, which runs before a
    pack is active); prefer :func:`active_snapshot_codes` on the live grade path, where the
    active pack resolves the snapshot.
    """
    data = json.loads(Path(path).read_text())
    codes: set[str] = set()
    for tier_codes in data["tiers"].values():
        codes.update(tier_codes)
    return codes


def active_snapshot_codes() -> frozenset[str]:
    """The active workspace's pack KNOWN_TAXONOMY_CODES (the TIER_1|2|3 union) — the gradeable gate.

    PACK-DIST-1: the taxonomy snapshot relocated OUT of the repo, so the old hardcoded
    ``packs/healthcare/taxonomy_snapshot.json`` read raises FileNotFoundError → 500 on every
    config-write gate. The BFF process is ``_core``-bound at import, so it resolves the ACTIVE
    WORKSPACE'S pack explicitly (``pack.active_pack()`` is ``_core`` here) — the same pack the
    subprocess grade binds. The pack must be discoverable (the global ``LITHRIM_BENCH_PACKS_DIR``
    / an installed wheel). The ``pack`` / ``workspace`` imports are LAZY so this module stays
    import-light on the BFF startup path.
    """
    from lithrim_bench.harness import pack as pack_mod
    from lithrim_bench.harness import workspace

    return pack_mod.pack_taxonomy_codes(workspace.get_active_workspace().pack)


def gradeable_flags_outside_snapshot(
    flags: list[dict], snapshot_codes: set[str] | frozenset[str]
) -> list[str]:
    """S-BS-10 lint: gradeable flags that the snapshot has NOT blessed (a failure).

    Pure so it is unit-testable on a crafted (flags, snapshot) pair. A non-empty return is
    a hard error: a ``gradeable`` flag whose code the snapshot (the contract-of-record) does
    not carry — re-snapshot (``scripts/snapshot_taxonomy.py``), never hand-edit. The live PUT
    gate refuses such a body (HTTP 422); the seed build raises ``SystemExit``.
    """
    return sorted(
        f["flag"] for f in flags if f.get("gradeable") and f["flag"] not in snapshot_codes
    )
