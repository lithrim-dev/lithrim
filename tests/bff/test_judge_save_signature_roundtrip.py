"""REPLAY-HONESTY-1 / UI-pass 2026-07-04 finding #4 — the judge-save ⇄ grade-signature contract.

SIGNATURE-1 made criterion/k/temperature grade-signature inputs, so a judge edit correctly
invalidates the $0-replay baseline (a 409 until re-graded). The flip side must ALSO hold, or
the editor becomes a replay-destroying trap:

  * a k/temperature edit **moves** the signature (non-vacuous — the SIGNATURE-1 direction);
  * saving the edit **back** (the JudgeEditor revert payload: the cleared field is OMITTED,
    not sent as 0/null) **restores** the signature byte-identically — save-then-revert must
    round-trip, no field may be silently normalized (None → 0.0) into a permanent drift;
  * a NO-OP save of a create-path judge (POST /v1/judges stores dataclass defaults:
    temperature=None, k=None, criterion="") leaves the signature unchanged — "open the judge
    card and click Save" must not invalidate every saved baseline.

The signature inputs are computed EXACTLY as the grade site does (scripts/run_eval.py:
list_judges → the assignments/models/samples/temperatures/criteria comprehensions), so a
drift here IS a replay-freshness 409 on the product. $0/offline; a throwaway tmp config DB.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

from lithrim_bench.harness.audit import Actor  # noqa: E402
from lithrim_bench.harness.judges import (  # noqa: E402
    JudgeConfig,
    judge_to_dict,
    list_judges,
    save_judge,
)
from lithrim_bench.harness.replay import grade_signature  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

ROLE = "risk_judge"


def _put(db_path: Path, body: dict) -> dict:
    return bff.put_judge_endpoint(
        role=ROLE,
        judge=body,
        rationale="signature round-trip test",
        agent=None,
        db_path=db_path,
        default_actor=Actor(type="system", id="test"),
        x_actor=None,
    )


def _signature(db_path: Path) -> str:
    """The grade-determining hash over the SAME judges-store projections the grade site
    builds (scripts/run_eval.py) — ontology/council_config held constant, so any movement
    comes from the judge save under test."""
    cfg = list_judges(db_path=db_path)
    return grade_signature(
        {"flags": ["FABRICATED_CLAIM"]},
        assignments={r: jc.assigned_flags for r, jc in cfg.items() if jc.assigned_flags},
        models={r: jc.model for r, jc in cfg.items() if jc.model},
        council_config={"reviewer_roster": [ROLE]},
        criteria={r: jc.criterion for r, jc in cfg.items() if jc.criterion},
        samples={r: jc.k for r, jc in cfg.items() if jc.k is not None},
        temperatures={r: jc.temperature for r, jc in cfg.items() if jc.temperature is not None},
        demo_digests={},
    )


# the JudgeEditor persist() payload shape: model/assigned/validators/criterion ALWAYS sent;
# k/temperature sent ONLY when the input is non-empty (clearing the field omits the key).
_CARD_BASE = {"model": "", "assigned_flags": [], "validator_refs": [], "criterion": ""}


def test_k_edit_moves_the_signature_and_the_card_revert_restores_it(tmp_path):
    db = tmp_path / "config.sqlite"
    _put(db, dict(_CARD_BASE))  # author the judge (the pre-edit baseline state)
    s0 = _signature(db)
    stored0 = judge_to_dict(list_judges(db_path=db)[ROLE])

    _put(db, {**_CARD_BASE, "k": 3})  # the SME edit
    assert _signature(db) != s0  # SIGNATURE-1: k IS grade-determining — the edit must invalidate

    _put(db, dict(_CARD_BASE))  # the card revert: k cleared → key omitted
    assert _signature(db) == s0  # save-then-revert restores $0 replayability
    assert judge_to_dict(list_judges(db_path=db)[ROLE]) == stored0  # byte-identical stored config


def test_temperature_edit_round_trips_too(tmp_path):
    db = tmp_path / "config.sqlite"
    _put(db, dict(_CARD_BASE))
    s0 = _signature(db)

    _put(db, {**_CARD_BASE, "temperature": 0.7})
    assert _signature(db) != s0

    _put(db, dict(_CARD_BASE))
    assert _signature(db) == s0


def test_noop_card_save_of_a_create_path_judge_does_not_drift_the_signature(tmp_path):
    """POST /v1/judges persists JudgeConfig dataclass defaults (temperature=None, k=None,
    criterion="") — replicated here via the same save_judge call it makes. A JudgeEditor
    no-op save (open the card, click Save) must store the identical config: no silent
    None→0.0 normalization may invalidate every saved baseline."""
    db = tmp_path / "config.sqlite"
    save_judge(JudgeConfig(role=ROLE, model="", assigned_flags=(), validator_refs=()), db_path=db)
    s0 = _signature(db)
    stored0 = judge_to_dict(list_judges(db_path=db)[ROLE])

    _put(db, dict(_CARD_BASE))  # the card's no-op save
    assert judge_to_dict(list_judges(db_path=db)[ROLE]) == stored0
    assert _signature(db) == s0
