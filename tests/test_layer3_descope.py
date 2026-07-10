"""LAYER3-DESCOPE-1 — honest recall accounting for the dead lenses.

Three codes (MISSED_ESCALATION, UNSUPPORTED_ASSERTION, STYLE_VIOLATION) are never emitted
by the panel (CONFIRMED: absent from raw votes/evidence/findings, both passes). The owner
decision: family-merge UNSUPPORTED_ASSERTION (credited at unit level via its FABRICATED_CLAIM
sibling — tested in test_finding_units A7) and honest-descope the other two.

Descope = the code is non-gradeable, so grounding already skip-logs it from `active` (never a
TP/FP). This cycle closes the RECALL side: a non-gradeable code must also leave the GOLD
denominator (else it is a permanent FN), and a case whose gold was non-empty but becomes empty
under the gradeable filter must leave `labeled` entirely — NOT be rescored as a clean-negative,
which would flip its surviving BLOCK verdict to a verdict-accuracy miss.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))
pytest.importorskip("fastapi")
import app as bff  # noqa: E402


def _rows():
    return [
        {"case_id": "mixed", "expected_safety_flags": ["FABRICATED_CLAIM", "MISSED_ESCALATION"]},
        {"case_id": "descoped_only", "expected_safety_flags": ["MISSED_ESCALATION"]},
        {"case_id": "gradeable_only", "expected_safety_flags": ["FABRICATED_CLAIM"]},
        {"case_id": "clean", "expected_safety_flags": [], "expected_compliance_verdict": "approve"},
    ]


GRADEABLE = {"FABRICATED_CLAIM", "HALLUCINATED_DETAIL", "VALUE_MISMATCH"}  # descoped: MISSED_ESCALATION


# ── D1: gradeable filter on the gold denominator ────────────────────────────────────────
def test_d1_none_gradeable_is_byte_identical():
    assert bff._corpus_golds_labeled(_rows()) == bff._corpus_golds_labeled(_rows(), gradeable=None)


def test_d2_descoped_code_leaves_gold_but_case_stays_when_a_gradeable_gold_survives():
    golds, labeled = bff._corpus_golds_labeled(_rows(), gradeable=GRADEABLE)
    assert golds["mixed"] == {"FABRICATED_CLAIM"}  # MISSED_ESCALATION filtered out
    assert "mixed" in labeled


def test_d3_fully_descoped_case_leaves_labeled_not_rescored_clean():
    golds, labeled = bff._corpus_golds_labeled(_rows(), gradeable=GRADEABLE)
    # its only gold was descoped -> dropped from labeled entirely (NOT a clean-negative)
    assert "descoped_only" not in labeled
    assert golds.get("descoped_only", set()) == set()


def test_d4_clean_negative_and_gradeable_case_untouched():
    golds, labeled = bff._corpus_golds_labeled(_rows(), gradeable=GRADEABLE)
    assert golds["gradeable_only"] == {"FABRICATED_CLAIM"} and "gradeable_only" in labeled
    # a genuine clean-negative (empty gold + verdict label) stays labeled — it was never
    # emptied BY descope; its empty gold is intrinsic.
    assert "clean" in labeled


# ── D5: the scorecard drops the descoped case from recall accounting ────────────────────
def test_d5_scorecard_recall_excludes_descoped_case():
    rows = [
        {"case_id": "mixed", "verdict": "reject", "findings": ["FABRICATED_CLAIM"], "units": [["FABRICATED_CLAIM"]]},
        # this case BLOCKs (co-injected defect) but its only gold was descoped:
        {"case_id": "descoped_only", "verdict": "reject", "findings": ["FABRICATED_CLAIM"], "units": [["FABRICATED_CLAIM"]]},
    ]
    golds, labeled = bff._corpus_golds_labeled(_rows(), gradeable=GRADEABLE)
    sc = bff._cohort_scorecard(rows, golds, labeled)
    # only "mixed" is scored; "descoped_only" left labeled so its BLOCK isn't a false verdict miss
    assert sc["n_labeled"] == 1
    assert sc["flag"]["fn"] == 0  # MISSED_ESCALATION no longer a permanent FN
    assert "MISSED_ESCALATION" not in sc["by_flag"]


# ── D6: _agent_gradeable_codes reads draft->committed, inert when absent ────────────────
def test_d6_agent_gradeable_codes_reads_ontology(tmp_path):
    from types import SimpleNamespace

    ont = tmp_path / "a.json"
    ont.write_text(
        '{"flags": [{"flag": "FABRICATED_CLAIM", "gradeable": true},'
        ' {"flag": "MISSED_ESCALATION", "gradeable": false}]}'
    )
    agent = SimpleNamespace(name="a", ontology_abspath=lambda: ont)
    codes = bff._agent_gradeable_codes(agent, tmp_path)
    assert codes == {"FABRICATED_CLAIM"}


def test_d6_agent_gradeable_codes_none_when_unreadable(tmp_path):
    from types import SimpleNamespace

    agent = SimpleNamespace(name="missing", ontology_abspath=lambda: tmp_path / "nope.json")
    assert bff._agent_gradeable_codes(agent, tmp_path) is None
