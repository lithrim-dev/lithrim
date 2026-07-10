"""Normalize the bidirectional subsumption corpus into BLIND, FINDING-LOCAL fixtures.

CRITERION-JUTE-1c deliverable 1. Reads the 44 source cases (22 upcoded positives +
22 clean-generalization negatives) from the main-tree
``docs/clinverdict/bidirectional_proposal/`` and rewrites each as a fixture case that
carries a synthesized, finding-local code block. The source strata leak the answer in
their key NAMES (positives use ``record_parent_snomed`` / ``note_child_snomed``;
negatives use ``record_child_snomed`` / ``note_parent_snomed``), so at grade time we do
NOT read ``pinned.subsumption`` — instead every case gets a ``_synth_findings`` list whose
codes sit at STABLE, blind keys (``record_snomed`` / ``note_snomed``, matching the 1b
fixtures per S-CRITERION-JUTE-2). ``pinned.subsumption`` is kept untouched for provenance.

RECORD code = the record's snomed  (positives: record_parent_snomed;  negatives: record_child_snomed)
NOTE   code = the note's   snomed  (positives: note_child_snomed;    negatives: note_parent_snomed)

The note TERM is the note's PMH span text (the evidence span the finding flagged): the
child term for a positive (the upcoded, more-specific note diagnosis), the parent term for
a negative (the generalized note diagnosis).

Two source codes carry a trailing ``(verify)`` annotation (a data-provenance note, not part
of the numeric id); we strip it so the code is a clean SNOMED integer string.

Run (from the worktree root):
    python tests/fixtures/subsumption_bidirectional/_normalize.py

It regenerates ``upcoded_positives.jsonl`` and ``clean_generalization_negatives.jsonl`` in
this directory. The regeneration is deterministic; the checked-in fixtures ARE its output.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]

# The read-only source corpus (a maintainer-local research tree, absent on a public clone).
# Deliverable 1 copies FROM here; override with LITHRIM_BENCH_SUBSUMPTION_SOURCE_DIR.
SOURCE_DIR = Path(
    os.environ.get(
        "LITHRIM_BENCH_SUBSUMPTION_SOURCE_DIR",
        str(_REPO_ROOT / "docs" / "clinverdict" / "bidirectional_proposal"),
    )
)
OUT_DIR = Path(__file__).resolve().parent

FLAG_CODE = "UPCODED_DIAGNOSIS"


def _clean_code(raw: str) -> str:
    """Strip a trailing ``(verify)`` provenance annotation; keep the bare SNOMED id string."""
    return re.sub(r"\s*\(verify\)\s*$", "", str(raw)).strip()


def canonical_pair(case: dict) -> tuple[str, str, str, str]:
    """The blind (record_code, note_code, record_term, note_term) for a case, polarity-agnostic.

    Reads whichever stratum key set is present. record_* is the record's concept; note_* is the
    note's concept (the flagged span). No parent/child hint survives into the returned tuple.
    """
    sub = case["pinned"]["subsumption"]
    record_code = _clean_code(sub.get("record_parent_snomed") or sub.get("record_child_snomed"))
    note_code = _clean_code(sub.get("note_child_snomed") or sub.get("note_parent_snomed"))
    record_term = sub.get("record_parent") or sub.get("record_child")
    note_term = sub.get("note_child") or sub.get("note_parent")
    return record_code, note_code, record_term, note_term


def synth_findings(case: dict) -> list[dict]:
    """One finding per case, finding-local + blind: the flagged note span + its (record, note) codes."""
    record_code, note_code, _record_term, note_term = canonical_pair(case)
    return [
        {
            "flag_code": FLAG_CODE,
            "_evidence_spans": [note_term],
            "subsumption_codes": {"record_snomed": record_code, "note_snomed": note_code},
        }
    ]


def normalize_case(case: dict) -> dict:
    """Return a copy with ``_synth_findings`` added; ``pinned`` left intact for provenance."""
    out = dict(case)
    out["_synth_findings"] = synth_findings(case)
    return out


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def main() -> None:
    if not SOURCE_DIR.is_dir():
        raise SystemExit(
            f"source corpus not found: {SOURCE_DIR} (maintainer-only regeneration input; "
            "set LITHRIM_BENCH_SUBSUMPTION_SOURCE_DIR)"
        )
    for name in ("upcoded_positives.jsonl", "clean_generalization_negatives.jsonl"):
        src = SOURCE_DIR / name
        rows = [normalize_case(c) for c in load_jsonl(src)]
        write_jsonl(OUT_DIR / name, rows)
        print(f"wrote {len(rows)} cases -> {OUT_DIR / name}")


if __name__ == "__main__":
    main()
