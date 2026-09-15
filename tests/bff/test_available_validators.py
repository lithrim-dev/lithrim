"""VALIDATOR-OFFER-1: the reviewer editor offers only fact-checks this pack can actually run.

GET /v1/judges/{role} returned the static `_KNOWN_VALIDATORS` tuple whatever the workspace's
pack was, so the neutral `_core` pack offered `dosage_grounding` — a clinical floor whose tool
class and executor ship in the healthcare pack. Attaching it authored a reference nothing could
execute. The offer is now resolved like the grounding contract types are (`_grounding_contract_types`
resolves the ACTIVE workspace's pack, so OFFER and GATE agree): a name is offered when this pack
registers an executor for it or core implements its verification tool."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402


def test_the_neutral_pack_never_offers_the_clinical_floor():
    offered = bff._available_validators("_core")
    assert "dosage_grounding" not in offered, "a clinical floor on the neutral pack"


def test_it_still_offers_what_core_can_run():
    offered = bff._available_validators("_core")
    assert "structural_jute" in offered and "kb_rag" in offered


def test_every_offered_name_is_one_the_spec_accepts():
    from lithrim_bench.verification import spec as _spec

    assert set(bff._available_validators("_core")) <= set(_spec._KNOWN_TOOLS)


def test_the_offer_is_a_subset_of_the_known_validators_and_stays_ordered():
    offered = bff._available_validators("_core")
    known = list(bff._KNOWN_VALIDATORS)
    assert set(offered) <= set(known)
    assert offered == [v for v in known if v in set(offered)], "the tuple's order is kept"


def test_an_undiscoverable_pack_falls_back_to_the_core_offer_rather_than_failing():
    assert bff._available_validators("no_such_pack_here") == bff._available_validators("_core")
