"""Picklist case-fixture resolution shared between validation + pack-author scripts.

Factored out of ``scripts/validate_canonical_12_via_sdk.py`` 2026-05-28 (cycle
P1-CANONICAL-PACK, S-P1-11 hygiene): both the validation harness and the
canonical-pack builder need to map a picklist ``case_id`` back to the original
synthesized bench row (transcript + artifacts + provenance). Keeping the
resolver in one place avoids drift between the two consumers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

# Pack-name -> fixture-file resolution. Verified 2026-05-28: every picklist
# case_id resolves cleanly via this map.
PACK_FILES: dict[str, list[Path]] = {
    "scribe_v1": [
        REPO_ROOT / "out" / "scribe_v1.n10.jsonl",
        REPO_ROOT / "out" / "scribe_v1.jsonl",
    ],
    "scheduling_v1": [
        REPO_ROOT / "out" / "scheduling_v1.n10.jsonl",
        REPO_ROOT / "out" / "scheduling_v1.jsonl",
    ],
    "coding_v1": [
        REPO_ROOT / "out" / "coding_v1.jsonl",
    ],
    "triage_v1": [
        REPO_ROOT / "out" / "triage_v1.n10.jsonl",
        REPO_ROOT / "out" / "triage_v1.jsonl",
    ],
    "hl7_adt_v1": [
        REPO_ROOT / "out" / "hl7_adt_v1.jsonl",
    ],
}


def resolve_case_fixtures(case_ids: set[str]) -> dict[str, dict[str, Any]]:
    """Walk the bench's pack files; return ``case_id -> fully-loaded case row``.

    Identical semantics to the original
    ``scripts/validate_canonical_12_via_sdk.py:_resolve_case_fixtures`` so
    callers can be swapped one-for-one.
    """
    found: dict[str, dict[str, Any]] = {}
    for _pack_name, paths in PACK_FILES.items():
        for fp in paths:
            if not fp.exists():
                continue
            for line in fp.open():
                row = json.loads(line)
                cid = row.get("case_id") or row.get("id")
                if cid in case_ids and cid not in found:
                    found[cid] = row
    return found
