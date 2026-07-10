"""NARR-5-CRIT-a — POST /v1/criterion (the audited self-serve gradeable-criterion endpoint).

The thin BFF wrapper over ``harness.criterion.splice_gradeable_criterion``: resolve the active
WORKSPACE pack → splice the snapshot → append the ``gradeable=True`` ontology flag (overlay) under
the now-passing admissibility lint → ONE AuditRecord, all atomic (snapshot rolled back if the
ontology write fails). Plus the tier-aware fix to the misleading 422 (a core pack points the SME at
create_gradeable_criterion, not the clinical backend re-snapshot).

Written RED-first: ``create_criterion_endpoint`` does not exist yet and ``_validate_ontology``'s
422 still emits the backend-re-snapshot message for a core pack. Runs $0/offline; needs the [bff]
extra. The active pack is a throwaway copy of ``packs/_core`` (no repo-source mutation).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

from lithrim_bench.harness.audit import Actor  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_AGENT = "ws0_default"


def _make_pack(tmp_path: Path, name: str, tier: str = "core") -> str:
    dst = tmp_path / name
    shutil.copytree(REPO_ROOT / "packs" / "_core", dst)
    m = json.loads((dst / "pack.json").read_text())
    m["pack_id"] = name
    m["tier"] = tier
    (dst / "pack.json").write_text(json.dumps(m, indent=2))
    return name


@pytest.fixture
def core_ws(tmp_path, monkeypatch):
    """Active workspace pinned to a throwaway tier:core pack; returns (pack_id, audit_records)."""
    from lithrim_bench.harness import pack as pack_mod
    from lithrim_bench.harness.workspace import Workspace

    name = _make_pack(tmp_path, "corepack", tier="core")
    existing = os.environ.get("LITHRIM_BENCH_PACKS_DIR", "")
    monkeypatch.setenv(
        "LITHRIM_BENCH_PACKS_DIR", str(tmp_path) + (os.pathsep + existing if existing else "")
    )
    pack_mod._pack_root.cache_clear()
    pack_mod._council_known_codes.cache_clear()
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda: Workspace(name="t", pack=name))
    records: list = []
    monkeypatch.setattr(bff.AuditLog, "record", lambda self, rec: records.append(rec))
    yield name, records
    pack_mod._pack_root.cache_clear()
    pack_mod._council_known_codes.cache_clear()


def _req(**kw):
    return bff.CriterionRequest(**kw)


def _call(tmp_path, body):
    """Call the endpoint fn directly with ALL params explicit (the FieldInfo-sentinel trap)."""
    return bff.create_criterion_endpoint(
        body=body,
        agent=_AGENT,
        rationale="the SME's why",
        db_path=tmp_path / "config.sqlite",
        workdir=tmp_path / "wd",
        default_actor=Actor(type="system", id="test"),
        x_actor=None,
    )


def _snapshot(pack: str) -> dict:
    from lithrim_bench.harness import pack as pack_mod

    return json.loads(pack_mod._pack_ref(pack, "flags_ref").read_text())


# ── A1 — happy path: snapshot spliced + ontology flag appended + ONE audit ──


def test_create_criterion_splices_snapshot_and_appends_flag(core_ws, tmp_path):
    from lithrim_bench.harness import pack as pack_mod

    pack, records = core_ws
    out = _call(tmp_path, _req(code="EVERY_DOSE_IN_SOAP", tier="TIER_2", owner_role="faithfulness_judge"))
    assert out["status"] == "ok" and out["code"] == "EVERY_DOSE_IN_SOAP" and out["pack"] == pack

    # snapshot: code in the tier union + the owner's lens (the withstands scope)
    assert "EVERY_DOSE_IN_SOAP" in pack_mod.pack_taxonomy_codes(pack)
    assert "EVERY_DOSE_IN_SOAP" in _snapshot(pack)["lenses"]["faithfulness_judge"]

    # ontology overlay: the gradeable flag was appended
    overlay = json.loads((tmp_path / "wd" / f"{_AGENT}.json").read_text())
    flag = next((f for f in overlay["flags"] if f["flag"] == "EVERY_DOSE_IN_SOAP"), None)
    assert flag is not None
    assert flag["gradeable"] is True and flag["tier"] == "TIER_2" and flag["owner_roles"] == ["faithfulness_judge"]

    # ONE audit record for the criterion
    crit_audits = [r for r in records if r.target.type == "criterion"]
    assert len(crit_audits) == 1 and crit_audits[0].target.id == "EVERY_DOSE_IN_SOAP"


# ── A2 — after create, the gradeable flag VALIDATES (the re-snapshot 422 does NOT fire) ──


def test_after_create_the_gradeable_flag_validates(core_ws, tmp_path):
    pack, _ = core_ws
    _call(tmp_path, _req(code="EVERY_DOSE_IN_SOAP", tier="TIER_2", owner_role="faithfulness_judge"))
    overlay = json.loads((tmp_path / "wd" / f"{_AGENT}.json").read_text())
    # the overlay (carrying the new gradeable flag) passes the gradeable gate now — no 422
    bff._validate_ontology(overlay)


# ── A3 / A4 / A5 — the rejections map to the right HTTP status, snapshot untouched ──


def test_bad_owner_422(core_ws, tmp_path):
    from fastapi import HTTPException

    pack, _ = core_ws
    before = _snapshot(pack)
    with pytest.raises(HTTPException) as ei:
        _call(tmp_path, _req(code="X_CODE", tier="TIER_2", owner_role="not_a_judge"))
    assert ei.value.status_code == 422
    assert _snapshot(pack) == before


def test_duplicate_409(core_ws, tmp_path):
    from fastapi import HTTPException

    pack, _ = core_ws
    with pytest.raises(HTTPException) as ei:
        _call(tmp_path, _req(code="STYLE_VIOLATION", tier="TIER_3", owner_role="policy_judge"))
    assert ei.value.status_code == 409


def test_non_core_pack_422(tmp_path, monkeypatch):
    from fastapi import HTTPException

    from lithrim_bench.harness import pack as pack_mod
    from lithrim_bench.harness.workspace import Workspace

    name = _make_pack(tmp_path, "propack", tier="pro")
    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(tmp_path))
    pack_mod._pack_root.cache_clear()
    pack_mod._council_known_codes.cache_clear()
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda: Workspace(name="t", pack=name))
    monkeypatch.setattr(bff.AuditLog, "record", lambda self, rec: None)
    with pytest.raises(HTTPException) as ei:
        _call(tmp_path, _req(code="X_CODE", tier="TIER_2", owner_role="faithfulness_judge"))
    assert ei.value.status_code == 422
    pack_mod._pack_root.cache_clear()


# ── S-BS-142 — a PRE-EXISTING out-of-snapshot gradeable flag must NOT block minting a NEW
#    admissible criterion. The endpoint lints ONLY the net-new code (which the splice just blessed),
#    not the whole agent ontology — a flag admitted under a DIFFERENT pack is not the new request's
#    concern. (Endpoint ATOMICITY is covered by F2 below, via a failing audit write — a trigger that
#    survives this fix; this test previously USED the whole-ontology lint as its rollback trigger,
#    which WAS the S-BS-142 bug, so it is repurposed into the regression test.) ──


def test_preexisting_out_of_snapshot_flag_does_not_block_mint(core_ws, tmp_path):
    from lithrim_bench.harness import pack as pack_mod

    pack, _ = core_ws
    # the cross-pack reality: the agent's ontology carries a gradeable flag the ACTIVE pack's
    # snapshot never blessed (it was admitted under a different pack). Re-linting the WHOLE ontology
    # used to 422 the new criterion; the endpoint must lint only the net-new code.
    wd = tmp_path / "wd"
    wd.mkdir(parents=True, exist_ok=True)
    preexisting = {
        "ontology_version": "t/v1",
        "domain": "test",
        "flags": [
            {"flag": "UNBLESSED_PREEXISTING", "category": "x", "definition": "", "when_to_use": "",
             "when_NOT_to_use": "", "owner_roles": ["policy_judge"], "tier": "TIER_2", "gradeable": True}
        ],
        "questions": [],
        "verification_contracts": [],
        "severity_map": {"weights": {}, "block_at_or_above": 1.0, "warn_above": 0.5},
    }
    (wd / f"{_AGENT}.json").write_text(json.dumps(preexisting))
    assert "UNBLESSED_PREEXISTING" not in pack_mod.pack_taxonomy_codes(pack)  # precondition: out-of-snapshot

    out = _call(tmp_path, _req(code="GOOD_CODE", tier="TIER_2", owner_role="faithfulness_judge"))
    assert out["status"] == "ok"  # S-BS-142 RED before the fix: 422 on UNBLESSED_PREEXISTING
    assert "GOOD_CODE" in pack_mod.pack_taxonomy_codes(pack)  # the net-new criterion is blessed
    final = {f["flag"] for f in json.loads((wd / f"{_AGENT}.json").read_text())["flags"]}
    assert {"GOOD_CODE", "UNBLESSED_PREEXISTING"} <= final  # new landed, pre-existing preserved (not dropped)


def test_validate_ontology_lint_flags_scopes_the_snapshot_check(core_ws, tmp_path):
    """The fix mechanism: ``_validate_ontology`` defaults to linting ALL flags (the PUT gate /
    labels-true-by-construction invariant, UNCHANGED), but ``lint_flags`` scopes the snapshot
    check to a subset — the criterion endpoint passes only the net-new code."""
    from fastapi import HTTPException

    pack, _ = core_ws
    foreign = {"flag": "FOREIGN_GRADEABLE", "category": "x", "definition": "", "when_to_use": "",
               "when_NOT_to_use": "", "owner_roles": ["policy_judge"], "tier": "TIER_2", "gradeable": True}
    ont = {"ontology_version": "t/v1", "domain": "test", "flags": [foreign], "questions": [],
           "verification_contracts": [], "severity_map": {"weights": {}, "block_at_or_above": 1.0, "warn_above": 0.5}}
    # DEFAULT (lint_flags=None): lints ALL flags → the foreign gradeable flag is rejected.
    with pytest.raises(HTTPException) as ei:
        bff._validate_ontology(ont)
    assert ei.value.status_code == 422
    # SCOPED: lint only an admissible subset (STYLE_VIOLATION ∈ _core snapshot) → the foreign flag
    # is NOT re-linted → no raise.
    admissible = {"flag": "STYLE_VIOLATION", "category": "x", "definition": "", "when_to_use": "",
                  "when_NOT_to_use": "", "owner_roles": ["policy_judge"], "tier": "TIER_3", "gradeable": True}
    bff._validate_ontology({**ont, "flags": [*ont["flags"], admissible]}, lint_flags=[admissible])  # no raise


# ── F1 — the request boundary refuses a malformed/empty code (no garbage into the snapshot) ──


def test_malformed_code_refused_at_boundary(core_ws, tmp_path):
    import pydantic

    pack, _ = core_ws
    before = _snapshot(pack)
    for bad in ["", "   ", "lower", "a;DROP", "HAS SPACE"]:
        with pytest.raises(pydantic.ValidationError):
            _req(code=bad, tier="TIER_2", owner_role="policy_judge")
    assert _snapshot(pack) == before


# ── F2 — an audit failure (AFTER splice+overlay) rolls BOTH the snapshot AND the overlay back ──


def test_audit_failure_rolls_back_snapshot_and_overlay(core_ws, tmp_path, monkeypatch):
    from lithrim_bench.harness import pack as pack_mod

    pack, _ = core_ws

    def _boom(self, rec):
        raise RuntimeError("audit db down")

    monkeypatch.setattr(bff.AuditLog, "record", _boom)
    before = _snapshot(pack)
    with pytest.raises(RuntimeError):
        _call(tmp_path, _req(code="ROLLBACK_CODE", tier="TIER_2", owner_role="policy_judge"))
    # the snapshot splice is undone — no un-audited mutation of the contract-of-record
    assert _snapshot(pack) == before
    assert "ROLLBACK_CODE" not in pack_mod.pack_taxonomy_codes(pack)
    # the ontology overlay is reverted too (it did not exist before this call)
    overlay = tmp_path / "wd" / f"{_AGENT}.json"
    assert not overlay.exists() or "ROLLBACK_CODE" not in overlay.read_text()


# ── F3 — the audit record captures the FULL governance delta (lenses + tier1_owners, not just tiers) ──


def test_audit_records_full_governance_delta(core_ws, tmp_path):
    pack, records = core_ws
    _call(tmp_path, _req(code="EVERY_DOSE_IN_SOAP", tier="TIER_2", owner_role="faithfulness_judge"))
    rec = next(r for r in records if r.target.type == "criterion")
    # the lenses raise-authority grant is in the canonical before→after diff (not only `tiers`)
    assert "EVERY_DOSE_IN_SOAP" in rec.after["lenses"]["faithfulness_judge"]
    assert "EVERY_DOSE_IN_SOAP" not in rec.before["lenses"]["faithfulness_judge"]
    assert "EVERY_DOSE_IN_SOAP" in rec.after["tiers"]["TIER_2_HIGH_RISK"]
    assert "tier1_owners" in rec.before and "tier1_owners" in rec.after


# ── A6 — the misleading 422 is tier-aware: a core pack points to create_gradeable_criterion ──


def test_core_pack_422_points_to_criterion_writer(core_ws, tmp_path):
    from fastapi import HTTPException

    # an UN-created gradeable flag still 422s on a core pack — but with the self-serve guidance,
    # NOT the clinical backend re-snapshot message (the misleading-422 fix).
    bad = {
        "ontology_version": "t/v1",
        "domain": "test",
        "flags": [
            {"flag": "NEVER_CREATED_CODE", "category": "x", "definition": "", "when_to_use": "",
             "when_NOT_to_use": "", "owner_roles": ["policy_judge"], "tier": "TIER_2", "gradeable": True}
        ],
        "questions": [],
        "verification_contracts": [],
        "severity_map": {"weights": {}, "block_at_or_above": 1.0, "warn_above": 0.5},
    }
    with pytest.raises(HTTPException) as ei:
        bff._validate_ontology(bad)
    assert ei.value.status_code == 422
    detail = ei.value.detail.lower()
    assert "create_gradeable_criterion" in detail or "/v1/criterion" in detail
    assert "backend" not in detail and "snapshot_taxonomy" not in detail
