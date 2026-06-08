"""Load the DOGFOOD-1 judge-set ladder from the config plane.

A *judge set* is one rung of the ladder: ``{label, models, assignments, roles, note}``.

  * ``models`` — per-role provider selector (``build_trio(models=)``). ``{}`` = all-Azure.
  * ``assignments`` — role → assigned ontology flag codes. The SAME assignments are
    applied to every set (the file's ``shared_assignments``) so all sets run through the
    authored trio + the withstands-gate; the only variable across the model-mix sets is
    ``models`` (an apples-to-apples composition contrast, no gate-on/off confound).
  * ``roles`` — an ordered subset of ``V2_ROLES`` (``None`` = the full trio). The
    roster-size ladder. A single-role roster is intentionally unsupported (the frozen
    ``_apply_consensus`` requires ``len(valid) >= 2``).

The loader is config-plane only — no council/dspy import — so the BFF/CLI can read a set
without the ``[council]`` extra.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JUDGE_SET_DIR = REPO_ROOT / "data" / "config" / "judge_sets"

JUDGESET_SCHEMA_VERSION = "judgeset/1"


def load_judge_sets(
    set_id: str = "dogfood_v1", *, judge_set_dir: str | Path | None = None
) -> list[dict[str, Any]]:
    """Return the resolved judge sets for ``set_id`` (each with shared assignments merged).

    The file's ``shared_assignments`` is applied to every set that does not declare its
    own ``assignments``. ``models`` defaults to ``{}`` (all-Azure) and ``roles`` to
    ``None`` (full trio) when omitted. Raises ``FileNotFoundError`` for an unknown id.
    """
    base = Path(judge_set_dir) if judge_set_dir is not None else DEFAULT_JUDGE_SET_DIR
    path = base / f"{set_id}.json"
    raw = json.loads(path.read_text())
    shared = raw.get("shared_assignments") or {}
    resolved: list[dict[str, Any]] = []
    for s in raw.get("sets") or []:
        resolved.append(
            {
                "label": s["label"],
                "models": s.get("models") or {},
                "assignments": s.get("assignments") or (dict(shared) if shared else None),
                "roles": s.get("roles"),
                "note": s.get("note", ""),
            }
        )
    return resolved


def get_judge_set(label: str, set_id: str = "dogfood_v1", **kw: Any) -> dict[str, Any]:
    """Return the one resolved set named ``label`` from ``set_id``. Raises ``KeyError``."""
    for s in load_judge_sets(set_id, **kw):
        if s["label"] == label:
            return s
    raise KeyError(f"judge set {label!r} not found in {set_id!r}")
