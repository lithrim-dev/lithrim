"""SHEPHERD-1c BFF acceptance — pack-aware offered lens (S-BS-154) + roster-add on
judge save (S-BS-153).

Hermetic, network-free, $0: drives the FastAPI BFF over a tmp config DB with the ACTIVE
WORKSPACE monkeypatched to ``pack=healthcare`` (the demo-clinical workspace's pack). Proves:

  - **S-BS-154** — with healthcare active, ``GET /v1/judges/{role}`` OFFERS the healthcare
    lens (a healthcare code present, the ``_core`` code ``INTERNAL_INCONSISTENCY`` absent),
    and the PUT gate ACCEPTS a healthcare code (200) while still rejecting a ``_core`` code
    (422) — OFFER and GATE agree on the active pack. The frozen module-global
    ``judge_metric.LENS_BY_ROLE`` is UNCHANGED (still the boot-pack value) — the fix lives in
    the BFF projection/gate, not the moat-load-bearing module global.
  - **S-BS-153** — ``PUT /v1/judges/{role}?agent=X`` adds ``role`` to ``X``'s
    ``eval_profile.judges`` (idempotent on repeat), writes an audit record, and does not touch
    other agents.

The healthcare pack must be discoverable (dev/CI: ``LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare``
or pip-installed). In a bare CE checkout it is nowhere → the module skips (the root-conftest
bare-CE demarcation, applied locally so this single-file proof is self-contained).
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness import pack as _pack
from lithrim_bench.harness.config import save_agent

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
from fastapi.testclient import TestClient  # noqa: E402

from tests._house_fixture import house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402


def _healthcare_discoverable() -> bool:
    try:
        _pack._pack_root("healthcare")
        return True
    except FileNotFoundError:
        return False


pytestmark = pytest.mark.skipif(
    not _healthcare_discoverable(),
    reason="bare CE — the healthcare pack is not discoverable (LITHRIM_BENCH_PACKS_DIR unset)",
)

_AGENT = "shepherd1c_test"
_OTHER = "shepherd1c_other"

# A healthcare risk_judge lens code (in the active-pack lens, NOT in _core) + the _core
# code that healthcare must reject. Resolved live from the pack so the test tracks the
# snapshot, not a hardcoded copy.
_HEALTH_RISK_CODE = "MISSED_ESCALATION"
_CORE_RISK_CODE = "INTERNAL_INCONSISTENCY"


def _empty_roster_agent(name: str):
    """A house agent whose roster is EMPTY (frozen dataclasses → ``dataclasses.replace``),
    so the S-BS-153 roster-add is observable from a clean precondition."""
    ag = house_agent(name=name)
    return dataclasses.replace(ag, eval_profile=dataclasses.replace(ag.eval_profile, judges=()))


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "bench_config.sqlite"
    # Two agents, each with an EMPTY roster, so the roster-add is observable.
    save_agent(_empty_roster_agent(_AGENT), db_path=p)
    save_agent(_empty_roster_agent(_OTHER), db_path=p)
    return p


@pytest.fixture
def coll_db(tmp_path):
    return tmp_path / "coll.sqlite"


@pytest.fixture
def client(tmp_path, db_path, coll_db, monkeypatch):
    # The ACTIVE workspace pins pack=healthcare (the demo-clinical pack) — the offer/gate
    # must track THIS pack, not the BFF boot pack (_core).
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="demo-clinical", pack="healthcare"),
    )
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: tmp_path / "out"
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: coll_db
    try:
        yield TestClient(bff.app)
    finally:
        bff.app.dependency_overrides.clear()


# ── S-BS-154: pack-aware offered lens (OFFER and GATE agree on the active pack) ──


def test_get_judge_offers_active_pack_lens(client):
    """With healthcare active, GET /v1/judges/{role} offers the HEALTHCARE lens — a
    healthcare code present, the _core code absent (the editor offers exactly what the
    gate accepts; the SHEPHERD-1b smoking gun is closed)."""
    body = client.get(f"/v1/judges/risk_judge?agent={_AGENT}").json()
    codes = {f["flag"] for f in body["available_flags"]}
    assert _HEALTH_RISK_CODE in codes  # the active-pack lens is offered
    assert _CORE_RISK_CODE not in codes  # the boot-pack code is NOT offered


def test_list_judges_enumerates_active_pack_roles(client):
    """GET /v1/judges enumerates the active-pack roles (healthcare's production_judges =
    the same trio) — the three reads (list/get/put) sit on one source of truth."""
    body = client.get(f"/v1/judges?agent={_AGENT}").json()
    assert set(body["roles"]) == set(_pack.pack_lenses("healthcare"))


def test_put_judge_accepts_active_pack_code(client):
    """The PUT gate ACCEPTS a healthcare lens code under the healthcare workspace (200) —
    offering it does not merely move the 422 from the snapshot-check to owner↔emit."""
    res = client.put(
        f"/v1/judges/risk_judge?agent={_AGENT}",
        json={"model": "", "assigned_flags": [_HEALTH_RISK_CODE], "validator_refs": []},
    )
    assert res.status_code == 200, res.text


def test_put_judge_rejects_core_code_under_healthcare(client):
    """The _core code is rejected (422) under the healthcare workspace — the owner↔emit
    gate tracks the active pack (NOT INTERNAL_INCONSISTENCY in healthcare's lens)."""
    res = client.put(
        f"/v1/judges/risk_judge?agent={_AGENT}",
        json={"model": "", "assigned_flags": [_CORE_RISK_CODE], "validator_refs": []},
    )
    assert res.status_code == 422, res.text


def test_module_global_lens_by_role_unchanged(client):
    """The frozen module-global judge_metric.LENS_BY_ROLE is NOT mutated by the BFF
    per-workspace resolution — the fix lives in the projection/gate, not the moat global
    (which is byte-imported by the byte-frozen signals.py as the withstands-gate default).
    Snapshot the global, exercise the per-request resolver under a healthcare workspace, and
    assert the global is identical — proving the BFF never reaches back into the moat global."""
    import lithrim_bench.runtime.council.judge_metric as jm

    before = dict(jm.LENS_BY_ROLE)
    # exercise the per-request resolver path (offer + gate, under healthcare)
    client.get(f"/v1/judges/risk_judge?agent={_AGENT}")
    client.put(
        f"/v1/judges/risk_judge?agent={_AGENT}",
        json={"model": "", "assigned_flags": [_HEALTH_RISK_CODE], "validator_refs": []},
    )
    assert before == jm.LENS_BY_ROLE  # the frozen module global is untouched (identity preserved)


def test_offer_tracks_active_workspace_not_the_boot_global(tmp_path, db_path, coll_db, monkeypatch):
    """The truly non-vacuous direction: with the active workspace flipped to a DIFFERENT
    pack than the boot global, the offered lens follows the ACTIVE WORKSPACE — proving the
    offer is resolved per-request (``_active_lens_by_role``), not from the frozen import-time
    ``LENS_BY_ROLE``. (The suite's boot pack is healthcare; the active workspace here is
    ``_core``, so the offer must carry the _core code and drop the healthcare one.)"""
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="ce", pack="_core"),
    )
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db_path
    bff.app.dependency_overrides[bff.get_out_dir] = lambda: tmp_path / "out"
    bff.app.dependency_overrides[bff.get_ontology_workdir] = lambda: tmp_path / "ont"
    bff.app.dependency_overrides[bff.get_collections_db] = lambda: coll_db
    try:
        c = TestClient(bff.app)
        codes = {
            f["flag"]
            for f in c.get(f"/v1/judges/risk_judge?agent={_AGENT}").json()["available_flags"]
        }
        assert _CORE_RISK_CODE in codes  # the ACTIVE (_core) lens is offered
        assert _HEALTH_RISK_CODE not in codes  # NOT the boot/healthcare lens
        # and the gate agrees: a _core code is accepted under the _core workspace
        res = c.put(
            f"/v1/judges/risk_judge?agent={_AGENT}",
            json={"model": "", "assigned_flags": [_CORE_RISK_CODE], "validator_refs": []},
        )
        assert res.status_code == 200, res.text
    finally:
        bff.app.dependency_overrides.clear()


# ── S-BS-153: roster-add on judge save (idempotent, audited, active-agent-only) ──


def test_put_judge_with_agent_rosters_idempotently(client):
    """PUT /v1/judges/{role}?agent=X adds role to X's eval_profile.judges and is a no-op
    on repeat (idempotent); it never touches another agent's roster."""
    # precondition: empty roster on both agents
    assert client.get(f"/v1/agent?name={_AGENT}").json()["eval_profile"]["judges"] == []
    assert client.get(f"/v1/agent?name={_OTHER}").json()["eval_profile"]["judges"] == []

    res = client.put(
        f"/v1/judges/risk_judge?agent={_AGENT}",
        json={"model": "", "assigned_flags": [_HEALTH_RISK_CODE], "validator_refs": []},
    )
    assert res.status_code == 200, res.text
    assert res.json()["rostered"] is True
    assert client.get(f"/v1/agent?name={_AGENT}").json()["eval_profile"]["judges"] == ["risk_judge"]
    # the OTHER agent is untouched
    assert client.get(f"/v1/agent?name={_OTHER}").json()["eval_profile"]["judges"] == []

    # repeat → idempotent (still a single entry; rostered now False)
    res2 = client.put(
        f"/v1/judges/risk_judge?agent={_AGENT}",
        json={"model": "", "assigned_flags": [_HEALTH_RISK_CODE], "validator_refs": []},
    )
    assert res2.status_code == 200
    assert res2.json()["rostered"] is False
    assert client.get(f"/v1/agent?name={_AGENT}").json()["eval_profile"]["judges"] == ["risk_judge"]


def test_put_judge_without_agent_does_not_roster(client):
    """No agent param → the per-role lens config saves but no roster is touched (the
    pre-S-BS-153 behavior is preserved when the caller does not ask for a roster add)."""
    res = client.put(
        "/v1/judges/risk_judge",
        json={"model": "", "assigned_flags": [_HEALTH_RISK_CODE], "validator_refs": []},
    )
    assert res.status_code == 200
    assert res.json()["rostered"] is False
    assert client.get(f"/v1/agent?name={_AGENT}").json()["eval_profile"]["judges"] == []


def test_roster_add_writes_an_audit_record(client):
    """The roster add goes through the audited put_agent_endpoint → an edit AuditRecord
    targets the agent (the §2B who/when/what/why for the roster change)."""
    client.put(
        f"/v1/judges/risk_judge?agent={_AGENT}",
        json={"model": "", "assigned_flags": [_HEALTH_RISK_CODE], "validator_refs": []},
    )
    rows = client.get(f"/v1/audit?target_type=agent&target_id={_AGENT}").json()["records"]
    # at least one agent-targeted edit record exists after the roster add (the §2B who/what/why)
    assert any(r.get("action") in {"edit", "author"} for r in rows), rows


def test_lens_edit_does_not_strip_existing_roster(client):
    """Editing a judge's lens again (a different code) must NOT remove the role from the
    roster — the roster add is monotone for a single-agent edit (idempotent no-op)."""
    client.put(
        f"/v1/judges/risk_judge?agent={_AGENT}",
        json={"model": "", "assigned_flags": [_HEALTH_RISK_CODE], "validator_refs": []},
    )
    assert client.get(f"/v1/agent?name={_AGENT}").json()["eval_profile"]["judges"] == ["risk_judge"]
    # re-edit the lens (still healthcare-valid) → roster unchanged
    other_code = next(
        c for c in _pack.pack_lenses("healthcare")["risk_judge"] if c != _HEALTH_RISK_CODE
    )
    client.put(
        f"/v1/judges/risk_judge?agent={_AGENT}",
        json={"model": "", "assigned_flags": [other_code], "validator_refs": []},
    )
    assert client.get(f"/v1/agent?name={_AGENT}").json()["eval_profile"]["judges"] == ["risk_judge"]
