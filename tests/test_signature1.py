"""SIGNATURE-1: the grade signature covers EVERYTHING that determines a grade.

The P0 it closes: per-judge ``criterion`` / ``k`` / ``temperature`` and the DEMO-PIN-1
compiled few-shot demos all thread into the grade but escaped ``grade_signature`` — so a $0
replay after a criterion edit served the PRE-edit verdict labeled FRESH. Widening the hash
makes the freshness guard honest again (existing heads become stale-by-construction: correct,
since they genuinely don't pin these inputs).

Also: the persisted head pins the grade-determining extras (``grade_config``) so the record
is self-describing about its inputs, not just carrying an opaque hash.

$0/offline, stdlib-only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.harness.replay import demo_digests, grade_signature, is_fresh  # noqa: E402

_ONT = {"domain": "d", "flags": []}
_BASE = dict(
    assignments={"risk_judge": ["A"]},
    models={"risk_judge": "gpt-4o"},
    council_config={"mode": "panel"},
    criteria={"risk_judge": "a positive abnormal assertion only"},
    samples={"risk_judge": 3},
    temperatures={"risk_judge": 0.2},
    demo_digests={"compiled_demos_1_risk_judge.json": "abc123"},
)


def _sig(**overrides) -> str:
    kw = {**_BASE, **overrides}
    return grade_signature(_ONT, **kw)


def test_identical_inputs_hash_identically():
    assert _sig() == _sig()


def test_each_grade_determining_axis_moves_the_signature():
    base = _sig()
    assert _sig(criteria={"risk_judge": "REWORDED criterion"}) != base
    assert _sig(samples={"risk_judge": 5}) != base
    assert _sig(temperatures={"risk_judge": 0.9}) != base
    assert _sig(demo_digests={"compiled_demos_1_risk_judge.json": "OTHER"}) != base
    assert _sig(models={"risk_judge": "gpt-4.1"}) != base


def test_the_stale_served_as_fresh_scenario_is_dead():
    """Edit a judge's criterion → the old head must NOT be fresh."""
    head = {"grade_signature": _sig()}
    assert is_fresh(head, _sig()) is True
    assert is_fresh(head, _sig(criteria={"risk_judge": "edited"})) is False


def test_demo_digests_are_content_sensitive(tmp_path):
    assert demo_digests(None) == {}
    assert demo_digests(tmp_path) == {}
    f = tmp_path / "compiled_demos_20260703_risk_judge.json"
    f.write_text(json.dumps([{"q": "x"}]))
    d1 = demo_digests(tmp_path)
    assert list(d1) == [f.name] and len(d1[f.name]) == 64
    f.write_text(json.dumps([{"q": "CHANGED"}]))
    d2 = demo_digests(tmp_path)
    assert d2[f.name] != d1[f.name]
    (tmp_path / "unrelated.json").write_text("{}")
    assert list(demo_digests(tmp_path)) == [f.name]  # only compiled_demos_* files count


def test_enrich_run_blob_pins_grade_config(tmp_path):
    """The head is self-describing: the grade-determining extras land in the blob."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import run_eval as re_mod

    from lithrim_bench.harness.backend import provenance_store_for

    db = tmp_path / "prov.sqlite"
    store = provenance_store_for(db)
    import asyncio

    asyncio.run(store.save_blob({"pipeline_run_id": "r-sig1", "verdict": "WARN"}))
    grade_config = {
        "models": {"risk_judge": "gpt-4o"},
        "criteria": {"risk_judge": "the criterion text"},
        "samples": {"risk_judge": 3},
        "temperatures": {"risk_judge": 0.2},
        "demo_digests": {},
    }
    re_mod._enrich_run_blob(
        "r-sig1", [], in_process=True, case_id="c1", agent_id="ag",
        grade_sig="sig-abc", grade_path="in_process", collections_db=db,
        grounded_block=None, grade_config=grade_config,
    )
    blob = asyncio.run(store.find_by_id("r-sig1"))
    assert blob["grade_config"] == grade_config
    assert blob["grade_signature"] == "sig-abc"


def test_replay_resolves_only_an_authoritative_head(tmp_path):
    """Caught live (2026-07-03 Docker validation): _resolve_from_provenance used latest_for,
    so a REPLAY row — stamped with the CURRENT signature at persist time — masqueraded as a
    fresh head and was served after a criterion edit. The replay baseline must be the newest
    AUTHORITATIVE row (replay_of falsy); its older signature then trips the freshness refusal."""
    import asyncio
    from types import SimpleNamespace

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import run_eval as re_mod

    from lithrim_bench.harness.backend import provenance_store_for

    db = tmp_path / "prov.sqlite"
    store = provenance_store_for(db)
    asyncio.run(store.save_blob({
        "pipeline_run_id": "auth-1", "verdict": "BLOCK", "agent_id": "ag", "case_id": "c1",
        "grade_signature": "OLD-SIG", "grade_path": "in_process",
    }))
    asyncio.run(store.save_blob({
        "pipeline_run_id": "replay-1", "verdict": "PASS", "agent_id": "ag", "case_id": "c1",
        "grade_signature": "CURRENT-SIG", "grade_path": "replay", "replay_of": "auth-1",
    }))
    agent = SimpleNamespace(name="ag", dataset=SimpleNamespace(case_id="c1"))
    # Config drifted since auth-1: the guard must REFUSE — never serve the replay row.
    try:
        re_mod._resolve_from_provenance(agent, "CURRENT-SIG", collections_db=db)
    except SystemExit as exc:
        assert "config changed" in str(exc)
    else:
        raise AssertionError("a replay row was served as a fresh head")
    # Same config as the authoritative head → served, and it IS the authoritative one.
    out = re_mod._resolve_from_provenance(agent, "OLD-SIG", collections_db=db)
    assert out["provenance"]["pipeline_run_id"] == "auth-1"
