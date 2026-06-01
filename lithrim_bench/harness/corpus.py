"""The correction corpus — a stable, versioned RLVR row over the correction stream.

WS-3a's :mod:`lithrim_bench.harness.correction` emits two *rich* record shapes —
``ws0-correction/1`` (a suppress: a confident FP the tool disproved) and
``ws3-floor-correction/1`` (a floor: a real violation the council missed and a
deterministic verifier caught). Those records are the lake (append-only NDJSON via
``correction.emit``). This module is the *projection* on top of them: a single,
direction-agnostic ``corpus-row/1`` that is the stable index an RLVR / fine-tuning
flywheel consumes. It WRAPS the existing records — it never re-authors them.

Why a projection and not a new label authority: the corpus is provenance, not a
fresh label. ``corpus-row/1`` carries the (case, corrected-flag, before→after
verdict, contract, owner_roles) tuple plus ``rollout_ref`` — a content digest that
points back to the full per-judge rollout in the correction lake, so the row stays
thin while the heavy rollout lives once in the lake.

Two facts about the source records that shape the row (both verified against
``correction.py`` builders, WS-4a plan-review):
  - Neither record carries ``case_id`` — it is threaded in from the run context.
  - The corrected flag is ``tool_call.flag_code`` in BOTH directions; the contract
    *identity* is ``tool_call.contract`` (suppress, the executor class name) or
    ``tool_call.contract_type`` (floor). ``action`` (from ``schema_version``)
    already encodes the direction, so no separate original/injected label field is
    needed — that distinction is the ``action``, not a column.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

CORPUS_SCHEMA_VERSION = "corpus-row/1"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS_PATH = REPO_ROOT / "out" / "ws4a" / "corpus.ndjson"

_SUPPRESS_PREFIX = "ws0-correction/"
_FLOOR_PREFIX = "ws3-floor-correction/"


def _action_for(record: dict[str, Any]) -> str:
    """Map a correction record's ``schema_version`` to its flywheel direction."""
    sv = record.get("schema_version", "")
    if sv.startswith(_SUPPRESS_PREFIX):
        return "suppress"
    if sv.startswith(_FLOOR_PREFIX):
        return "floor"
    raise ValueError(f"unrecognised correction schema_version {sv!r}")


def rollout_ref(record: dict[str, Any]) -> str:
    """Stable content id for a source correction record (the rollout pointer).

    ``sha256`` over the canonical (``sort_keys``) JSON — the same serialization
    discipline ``correction.emit`` writes the lake with, so the digest of a row in
    the lake matches :func:`rollout_ref` of the in-memory record byte-for-byte.
    """
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()


def project(record: dict[str, Any], *, case_id: str) -> dict[str, Any]:
    """Project one correction record into a ``corpus-row/1``.

    Direction-agnostic: reads ``tool_call.flag_code`` (the corrected flag) and the
    contract identity (``contract`` for suppress / ``contract_type`` for floor) off
    whichever shape the record is. ``case_id`` is supplied by the caller because the
    source records do not carry it (wrap-don't-re-author).
    """
    action = _action_for(record)
    tool_call = record.get("tool_call") or {}
    contract = tool_call.get("contract") if action == "suppress" else tool_call.get("contract_type")
    return {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "case_id": case_id,
        "action": action,
        "flag_code": tool_call.get("flag_code"),
        "verdict_before": record.get("composite_before"),
        "verdict_after": record.get("composite_after"),
        "contract": contract,
        "contract_version": record.get("contract_version"),
        "ontology_version": record.get("ontology_version"),
        "owner_roles": list(record.get("owner_roles") or ()),
        "rollout_ref": rollout_ref(record),
    }


def build_corpus(records: list[dict[str, Any]], *, case_id: str) -> list[dict[str, Any]]:
    """Project every correction record from one case into ``corpus-row/1`` rows."""
    return [project(rec, case_id=case_id) for rec in records]


def append_row(row: dict[str, Any], *, path: str | Path = DEFAULT_CORPUS_PATH) -> str:
    """Append one corpus row to the corpus NDJSON (append-only). Returns the path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    return str(p)


def read_corpus(path: str | Path = DEFAULT_CORPUS_PATH) -> Iterator[dict[str, Any]]:
    """Yield corpus rows back from the NDJSON (missing file -> no rows)."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.open():
        line = line.strip()
        if line:
            yield json.loads(line)
