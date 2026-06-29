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
    "fhir_patient_mini": [
        REPO_ROOT / "out" / "fhir_patient_mini.jsonl",
    ],
}


def resolve_case_fixtures(case_ids: set[str]) -> dict[str, dict[str, Any]]:
    """Walk the bench's pack files; return ``case_id -> fully-loaded case row``.

    Identical semantics to the original
    ``scripts/validate_canonical_12_via_sdk.py:_resolve_case_fixtures`` so
    callers can be swapped one-for-one.

    COLLISION-RESOLUTION ORDER (S-BS-9, documented + deterministic):
    ``PACK_FILES`` order is authoritative. Within a pack, the FIRST listed file
    wins on a ``case_id`` clash (``cid not in found`` keeps the first), so for
    ``scribe_v1`` the ``*.n10.jsonl`` file wins over the base ``*.jsonl`` — the same
    row may then carry a *different* ``expected_compliance_verdict`` shape (a list in
    n10 vs a bare string in the base file). Consumers that need a specific shape
    pin the source file explicitly via :func:`load_case` (the eval-profile
    ``dataset.source`` does this for the WS-0 case); the shape itself is normalized
    by :func:`normalize_expected_verdict`. No silent precedence beyond this rule.
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


# S-BS-9 shape contract: ``expected_compliance_verdict`` is EITHER a bare string
# verdict ("reject") OR an accept-set list of acceptable verdicts
# (["needs_review", "reject"]). Both normalize to a set of acceptable verdicts.
ACCEPTABLE_VERDICTS = {"approve", "needs_review", "reject"}


def normalize_expected_verdict(value: Any) -> set[str]:
    """Normalize either shape of ``expected_compliance_verdict`` to a verdict set."""
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, (list, tuple, set)):
        return {str(v) for v in value}
    raise ValueError(f"unsupported expected_compliance_verdict shape: {value!r}")


def expected_block(case: dict[str, Any]) -> bool:
    """True when 'reject' is (or is among) the case's expected compliance verdict.

    Subsumes the WS-0 ``run_ws0.expected_block`` shape-tolerant workaround into the
    single documented shape contract above.
    """
    return "reject" in normalize_expected_verdict(case.get("expected_compliance_verdict"))


def _load_from_workspace_corpus(case_id: str) -> dict[str, Any] | None:
    """Resolve ``case_id`` from the ACTIVE workspace's ingested corpus. PERSIST-3a: the SSOT
    ``cases`` table is the source of truth (``cases_store``, one DB selector), and the legacy
    ``ws.out_dir/ingested_cases.jsonl`` is a transition fallback (a corpus ingested before 3a, or
    a dual-written file). DB first, file second.

    Lazy in-fn import of :mod:`lithrim_bench.harness.workspace` (same core layer; the import is
    guarded so a bare-CE / no-workspace context degrades to ``None`` instead of raising). This is
    the STRICTLY-LAST fallback in :func:`load_case`, AFTER the explicit ``source`` pin (S-BS-9) and
    :func:`resolve_case_fixtures` (``PACK_FILES``), so an ingested case never shadows a pack case.
    """
    try:
        from lithrim_bench.harness import workspace
    except ImportError:
        return None
    try:
        ws = workspace.get_active_workspace()
    except Exception:  # noqa: BLE001 — a missing/unreadable workspace must not break resolution
        return None

    try:
        from lithrim_bench.harness import cases_store

        row = cases_store.load_case_row(case_id, db_path=ws.collections_db)
        if row is not None:
            return row
    except Exception:  # noqa: BLE001 — the DB read must not break the jsonl fallback
        pass

    corpus = ws.out_dir / "ingested_cases.jsonl"
    if not corpus.exists():
        return None
    for line in corpus.open():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if (row.get("case_id") or row.get("id")) == case_id:
            return row
    return None


def load_case(case_id: str, *, source: str | Path | None = None) -> dict[str, Any] | None:
    """Load one case row by id. If ``source`` is given, that file is pinned (the
    S-BS-9 source-pin); otherwise fall back to the documented pack resolution order, and — STRICTLY
    LAST — the active workspace's ingested corpus (S-BS-NARR2-1, the corpus-gradeable bridge).
    """
    if source is not None:
        source = Path(source)
        # is_file (not exists): a sourceless agent resolves source_abspath() to a DIRECTORY
        # (the repo root), and .open() on a dir raises IsADirectoryError — fall through instead.
        if source.is_file():
            for line in source.open():
                row = json.loads(line)
                if (row.get("case_id") or row.get("id")) == case_id:
                    return row
    pack_row = resolve_case_fixtures({case_id}).get(case_id)
    if pack_row is not None:
        return pack_row
    return _load_from_workspace_corpus(case_id)
