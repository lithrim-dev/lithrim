"""FAUTH-2 (G3 / OQ-2) — the author-time contract-type registration GATE + the live-types
endpoint.

The spine invariant's enforceable second half, moved UP to author time. Today
``_validate_ontology`` (``apps/bff/app.py``) checks ontology shape + the gradeable-flag
snapshot lint but NOT that each ``verification_contract.contract_type`` resolves to a
registered executor — so a bogus / free-text / ``openevidence_judge`` type is persistable
today and only detonates at GRADE time (``grounding.py`` raises "no executor registered for
contract_type X", a 500 mid-batch). This cycle gates the single write chokepoint
(``_put_grounding_contract`` — shared by the card POST and the ``add_grounding_contract``
chat tool) so a prose contract can never be pinned, plus a read-only
``GET /v1/grounding-contract/types`` that returns the active pack's registered executor keys.

READ-ONLY against the moat: the gate CALLS the public accessors
``grounding.suppress_executors()`` / ``floor_executors()`` — it does not edit ``grounding.py``,
``ground()``, or the executors.

These tests run $0/offline (no :3031, no LM, no paid council). They mirror the no-pin spy
pattern from ``test_ingest_cases_bound.py`` (a rejected contract pins NOTHING, audits NOTHING;
a registered one fires each spy once — non-vacuous both directions). Requires the ``[bff]``
extra (fastapi) + the healthcare pack discoverable (the canonical env
``LITHRIM_BENCH_PACKS_DIR=../lithrim-pack-healthcare LITHRIM_BENCH_PACK=healthcare``); skipped
cleanly otherwise so the default suite stays green.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

from lithrim_bench.harness import grounding  # noqa: E402
from lithrim_bench.harness.audit import Actor  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_AGENT = "ws0_default"


def _registered(pack: str | None = None) -> set[str]:
    """The registered executor set (suppress ∪ floor) for ``pack`` — the gate's truth. FAUTH-2a:
    defaults to the process pack; pass an explicit pack to mirror the endpoint, which now resolves
    the active WORKSPACE pack (so the assertion is order-independent vs the mutable workspace state)."""
    return set(grounding.suppress_executors(pack)) | set(grounding.floor_executors(pack))


def _seed_ontology(tmp_path: Path, flag_code: str = "MEDICATION_NOT_IN_TRANSCRIPT") -> Path:
    """Write a minimal working-copy ontology carrying one flag the contract can attach to.

    The working copy is ``<workdir>/<agent>.json`` (the path ``_resolve_ontology_path`` reads
    when one exists — so the gate runs against this, not the committed seed)."""
    import json

    ont = {
        "ontology_version": "test/v1",
        "taxonomy_version": "test",
        "domain": "test",
        "flags": [
            {
                "flag": flag_code,
                "category": "accuracy",
                "definition": "a test flag the contract attaches to",
                "when_to_use": "n/a (test)",
                "when_NOT_to_use": "n/a (test)",
                "gradeable": False,  # non-gradeable → no snapshot violation
            }
        ],
        "questions": [],
        "verification_contracts": [],
        "severity_map": {"weights": {}, "block_at_or_above": 1.0, "warn_above": 0.5},
    }
    (tmp_path / f"{_AGENT}.json").write_text(json.dumps(ont))
    return tmp_path / f"{_AGENT}.json"


def _real_ctx(tmp_path: Path):
    """A ToolContext carrying the REAL bound ``_put_grounding_contract`` over tmp paths."""
    return bff._build_tool_context(
        req_agent=_AGENT,
        db_path=tmp_path / "config.sqlite",
        out_dir=tmp_path / "out",
        workdir=tmp_path,
        collections_db=tmp_path / "collections.sqlite",
        actor=Actor(type="system", id="test"),
        x_actor=None,
    )


def _contracts(ont_path: Path) -> list[dict]:
    import json

    return json.loads(ont_path.read_text()).get("verification_contracts") or []


# ── A4: the live-types endpoint is pack-true + excludes prose ───────────────────────────


def test_grounding_contract_types_endpoint_is_pack_registered(tmp_path, monkeypatch):
    """GET /v1/grounding-contract/types returns exactly the active WORKSPACE pack's registered
    executor keys (suppress ∪ floor) — pinned against the LIVE registry, not a literal, so it
    can't drift. It INCLUDES presence_check + the pack's snomed_subsumption/record_presence and
    EXCLUDES any prose type.

    FAUTH-2a: the endpoint resolves ``get_active_workspace().pack`` (not the process env), so pin
    the active workspace to healthcare — else this is order-dependent on the mutable workspace state
    a prior full-suite test leaves behind (S-BS-FAUTH2-2)."""
    from lithrim_bench.harness.workspace import Workspace

    monkeypatch.setattr(
        bff.workspace, "get_active_workspace", lambda: Workspace(name="t", pack="healthcare")
    )
    reg = _registered("healthcare")
    out = bff.grounding_contract_types_endpoint()

    assert out["contract_types"] == sorted(reg)
    assert "presence_check" in out["contract_types"]
    # the pack-registered grounding types add_grounding_contract advertises
    assert "snomed_subsumption" in out["contract_types"]
    assert "record_presence" in out["contract_types"]
    # prose / free-text / future-LLM types are NOT registered → never offered
    assert "openevidence_judge" not in out["contract_types"]
    assert "negation_check" not in out["contract_types"]
    # non-empty (R3: if the set ever computed core-only/empty the gate would regress authoring)
    assert out["contract_types"]
    assert out["pack"] == "healthcare"


# ── A1: the author-time gate rejects an unregistered type, non-vacuously ─────────────────


def test_unregistered_contract_type_is_rejected(tmp_path):
    """POST the bound _put_grounding_contract with contract_type='openevidence_judge' on an
    EXISTING flag → 422, and NOTHING is persisted (verification_contracts unchanged). The gate
    front-runs the grade-time RAISE."""
    from fastapi import HTTPException

    ont_path = _seed_ontology(tmp_path)
    ctx = _real_ctx(tmp_path)

    with pytest.raises(HTTPException) as ei:
        ctx.put_grounding_contract(
            flag_code="MEDICATION_NOT_IN_TRANSCRIPT",
            contract_type="openevidence_judge",
            params={},
            question="bogus",
            version="x/v1",
            agent=_AGENT,
        )
    assert ei.value.status_code == 422
    assert "openevidence_judge" in str(ei.value.detail)
    # NOTHING persisted — the raise precedes put_ontology_endpoint.
    assert _contracts(ont_path) == []


def test_registered_contract_type_persists_non_vacuous(tmp_path):
    """The SAME call with a REGISTERED type (presence_check) succeeds + persists — proving the
    rejection above is the gate, not a broken happy path (non-vacuous)."""
    ont_path = _seed_ontology(tmp_path)
    ctx = _real_ctx(tmp_path)

    res = ctx.put_grounding_contract(
        flag_code="MEDICATION_NOT_IN_TRANSCRIPT",
        contract_type="presence_check",
        # GRADE-GUARD-1: valid presence_check params (the inert {"source":...} default is now 422'd)
        params={"med_source": "transcript", "dosage_regex": r"\b\d+\b"},
        question="Is the flagged medication actually present?",
        version="med/v1",
        agent=_AGENT,
    )
    assert res["flag_code"] == "MEDICATION_NOT_IN_TRANSCRIPT"
    pinned = _contracts(ont_path)
    assert len(pinned) == 1
    assert pinned[0]["contract_type"] == "presence_check"


def test_malformed_params_rejected_at_the_gate(tmp_path):
    """GRADE-GUARD-1: a REGISTERED type with MALFORMED params (a presence_check missing med_source —
    the inert-default footgun that crashed the live A-LIVE grade) is rejected 422 at the gate via the
    dry-construct validation, persisting NOTHING — so it can never detonate ground() at grade time.
    Non-vacuous vs the valid persist above (same type, only the params differ)."""
    from fastapi import HTTPException

    ont_path = _seed_ontology(tmp_path)
    ctx = _real_ctx(tmp_path)

    with pytest.raises(HTTPException) as ei:
        ctx.put_grounding_contract(
            flag_code="MEDICATION_NOT_IN_TRANSCRIPT",
            contract_type="presence_check",
            params={"source": "response.claims"},  # the inert default — no med_source/dosage_regex
            question="q",
            version="x/v1",
            agent=_AGENT,
        )
    assert ei.value.status_code == 422
    assert "med_source" in str(ei.value.detail)
    assert _contracts(ont_path) == []  # nothing persisted — the raise precedes put_ontology


def test_gate_precedence_404_unknown_flag_before_422(tmp_path):
    """Error precedence is stable: an UNKNOWN flag still 404s (before the type gate) even when
    the contract_type is also bogus — the 404 unknown-flag check is unchanged + comes first."""
    from fastapi import HTTPException

    _seed_ontology(tmp_path)
    ctx = _real_ctx(tmp_path)

    with pytest.raises(HTTPException) as ei:
        ctx.put_grounding_contract(
            flag_code="NO_SUCH_FLAG",
            contract_type="openevidence_judge",
            params={},
            agent=_AGENT,
        )
    assert ei.value.status_code == 404


# ── A2: the gate covers the chat path too, pins nothing ─────────────────────────────────


def _error_text(res: dict) -> str:
    return "".join(p.get("text", "") for p in (res.get("content") or []))


def test_add_grounding_contract_rejects_unregistered_type(tmp_path, monkeypatch):
    """add_grounding_contract_handler with a bogus type returns an error result (is_error, the
    "use a known contract_type" surface) and persists/audits ZERO times. The companion with a
    registered type fires the audit exactly once (non-vacuous both directions)."""
    from agent.tools import add_grounding_contract_handler

    _seed_ontology(tmp_path)
    ctx = _real_ctx(tmp_path)

    calls = {"audit": 0}

    class SpyAudit:
        def __init__(self, *_a, **_k):
            pass

        def record(self, *_a, **_k):
            calls["audit"] += 1

    monkeypatch.setattr(bff, "AuditLog", SpyAudit)

    # bogus type → is_error, nothing audited
    res = asyncio.run(
        add_grounding_contract_handler(
            ctx,
            {"flag_code": "MEDICATION_NOT_IN_TRANSCRIPT", "contract_type": "openevidence_judge"},
        )
    )
    assert res.get("is_error")
    assert "openevidence_judge" in _error_text(res) or "contract_type" in _error_text(res)
    assert calls["audit"] == 0  # NOTHING audited on a rejected contract

    # registered type → one audited write (the spies above are real, not dead)
    res2 = asyncio.run(
        add_grounding_contract_handler(
            ctx,
            {
                "flag_code": "MEDICATION_NOT_IN_TRANSCRIPT",
                "contract_type": "presence_check",
                # GRADE-GUARD-1: valid params (the inert {"source":...} default is now 422'd)
                "params": {"med_source": "transcript", "dosage_regex": r"\b\d+\b"},
            },
        )
    )
    assert not res2.get("is_error")
    assert calls["audit"] == 1  # audited exactly once


# ── FAUTH-2a: the gate/endpoint must resolve the ACTIVE WORKSPACE pack, not the process pack ──


def test_accessors_optional_pack_arg_is_additive():
    """grounding.suppress_executors()/floor_executors() take an optional pack= arg whose no-arg
    behavior is byte-identical to the explicit-default call (the moat read in signals.py / ground()
    is unaffected), and 'healthcare' is a strict superset of '_core' (the pack floors are present).

    This is the grounding.py-level half of the FAUTH-2a fix: the accessor is now pack-addressable
    so the BFF can ask for the WORKSPACE pack's set without rebinding the process env."""
    # no-arg == the explicit process-default (behavior-identical — the withstands-gate is unaffected)
    assert set(grounding.suppress_executors()) == set(
        grounding.suppress_executors(grounding._active_pack())
    )
    assert set(grounding.floor_executors()) == set(
        grounding.floor_executors(grounding._active_pack())
    )
    # healthcare ⊋ _core: the clinical floors are present ONLY under the healthcare pack
    core = set(grounding.suppress_executors("_core")) | set(grounding.floor_executors("_core"))
    hc = set(grounding.suppress_executors("healthcare")) | set(
        grounding.floor_executors("healthcare")
    )
    assert core < hc  # strict subset
    assert "record_presence" in hc and "record_presence" not in core
    assert {"snomed_subsumption", "dosage_grounding"} <= hc


def test_gate_resolves_the_active_workspace_pack_not_the_process_pack(tmp_path, monkeypatch):
    """The gate/endpoint must admit a type registered for the ACTIVE WORKSPACE'S grade pack, even
    when the BFF PROCESS pack differs — the live topology (process=_core, ws=healthcare graded via
    a subprocess bound to ws.pack). At parent 48162ad the gate reads the process env and false-
    rejects the pack floor (the live HTTP 422 the cold critic captured on clinical_scribe_clean).

    S-BS-FAUTH2-2. RED here, GREEN after both call sites resolve get_active_workspace().pack."""
    from fastapi import HTTPException

    from lithrim_bench.harness.workspace import Workspace

    # BFF process = _core (the live default — no LITHRIM_BENCH_PACK on the launcher)
    monkeypatch.delenv("LITHRIM_BENCH_PACK", raising=False)
    # the active workspace is pinned to healthcare (as clinical_scribe_clean is)
    monkeypatch.setattr(
        bff.workspace, "get_active_workspace", lambda: Workspace(name="t", pack="healthcare")
    )

    # (a) the endpoint returns the HEALTHCARE set (incl. record_presence), pack=healthcare
    out = bff.grounding_contract_types_endpoint()
    assert "record_presence" in out["contract_types"]
    assert "snomed_subsumption" in out["contract_types"]
    assert out["pack"] == "healthcare"

    # (b) the gate PERSISTS a record_presence contract on a healthcare-workspace flag (no 422)
    ont_path = _seed_ontology(tmp_path)
    ctx = _real_ctx(tmp_path)
    res = ctx.put_grounding_contract(
        flag_code="MEDICATION_NOT_IN_TRANSCRIPT",
        contract_type="record_presence",
        params={},
        question="Is the flagged item present in the record?",
        version="rp/v1",
        agent=_AGENT,
    )
    assert res["flag_code"] == "MEDICATION_NOT_IN_TRANSCRIPT"
    pinned = _contracts(ont_path)
    assert len(pinned) == 1
    assert pinned[0]["contract_type"] == "record_presence"

    # and prose is STILL rejected under the workspace pack (the FAUTH-2 win is not regressed)
    with pytest.raises(HTTPException) as ei:
        ctx.put_grounding_contract(
            flag_code="MEDICATION_NOT_IN_TRANSCRIPT",
            contract_type="openevidence_judge",
            params={},
            agent=_AGENT,
        )
    assert ei.value.status_code == 422
