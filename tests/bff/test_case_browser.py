"""CASE-BROWSER-1 (UI-pass 2026-07-04 finding #1) — GET /v1/cases/browser, the case-discovery read.

A tutorial reader cannot grade a case they cannot find: the pane's Cases tab listed only
fact-check corrections, so the loadable case IDs lived nowhere in the UI. This endpoint
serves the browsable union of every case ``load_case`` can resolve for the agent —
the agent's pinned source file, the legacy ``PACK_FILES`` fixtures, and the workspace's
ingested corpus (first-wins dedup in EXACTLY load_case's resolution order) — each row
carrying what the reader needs to pick one:

  * the by-construction label: ``labeled`` + ``defect`` (the injection_recipe's
    ``defect_type``, else the first expected flag; a labeled row with neither is a CLEAN
    negative; an unlabeled ingested row is honest "unknown ground truth");
  * ``runs`` — how many persisted runs this agent has for the case;
  * ``baseline`` — fresh | stale | none: whether the $0 replay would serve (the head's
    ``grade_signature`` vs the CURRENT signature). Freshness must be computed from the
    SAME input assembly the grade uses (``grade_signature_inputs``, shared with
    scripts/run_eval.py) or the dot lies — the manufactured-consistency failure mode.

$0/offline: tmp config DB, tmp source jsonl, a fake provenance store.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

from lithrim_bench.harness.judges import JudgeConfig, save_judge  # noqa: E402
from lithrim_bench.harness.replay import grade_signature, grade_signature_inputs  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

# ── the shared signature-input assembly (harness/replay.py) ──────────────────


def test_grade_signature_inputs_mirror_the_judges_store(tmp_path):
    db = tmp_path / "config.sqlite"
    save_judge(
        JudgeConfig(
            role="risk_judge",
            model="gpt-x",
            assigned_flags=("A", "B"),
            validator_refs=(),
            k=3,
            temperature=0.5,
            criterion="Reward only safe artifacts.",
        ),
        db_path=db,
    )
    save_judge(  # an all-defaults judge contributes NOTHING to any input dict
        JudgeConfig(role="policy_judge", model="", assigned_flags=(), validator_refs=()),
        db_path=db,
    )
    si = grade_signature_inputs(db, {}, lenses={})
    assert si["assignments"] == {"risk_judge": ("A", "B")}
    assert si["models"] == {"risk_judge": "gpt-x"}
    assert si["samples"] == {"risk_judge": 3}
    assert si["temperatures"] == {"risk_judge": 0.5}
    assert si["criteria"] == {"risk_judge": "Reward only safe artifacts."}


def test_grade_signature_inputs_seed_an_unauthored_roster_role_with_its_full_lens(tmp_path):
    """GENERALIST-1 parity: a reviewer_roster role the SME selected WITHOUT authoring a lens
    is seeded with its full pack lens (sorted) — exactly what run_eval main() hashes. An
    authored role and an off-lens role are untouched."""
    db = tmp_path / "config.sqlite"
    save_judge(
        JudgeConfig(role="authored", model="", assigned_flags=("Z",), validator_refs=()),
        db_path=db,
    )
    lenses = {"generalist": frozenset({"B", "A"}), "authored": frozenset({"Z", "Q"})}
    cc = {"reviewer_roster": ["generalist", "authored", "not_a_lens_role"]}
    si = grade_signature_inputs(db, cc, lenses=lenses)
    assert si["assignments"]["generalist"] == ("A", "B")  # seeded, sorted
    assert si["assignments"]["authored"] == ("Z",)  # authored lens NOT overwritten
    assert "not_a_lens_role" not in si["assignments"]


# ── the endpoint ──────────────────────────────────────────────────────────────


class _FakeStore:
    """latest_authoritative_for + list_all, async like the real store."""

    def __init__(self, docs, heads):
        self._docs, self._heads = docs, heads

    async def list_all(self, limit=500):
        return self._docs

    async def latest_authoritative_for(self, agent, case_id):
        return self._heads.get((agent, case_id))


class _Agent:
    name = "eval-1"

    def __init__(self, src: Path):
        self._src = src

    def source_abspath(self):
        return self._src

    class eval_profile:  # noqa: N801 — attribute-shape stub
        council_config: dict = {}


def _case_row(cid, *, recipe=None, flags=(), verdict=None):
    row = {"case_id": cid, "expected_safety_flags": list(flags), "injection_recipe": recipe}
    if verdict is not None:
        row["expected_compliance_verdict"] = verdict
    return row


@pytest.fixture()
def browser(tmp_path, monkeypatch):
    """Wire the endpoint's seams: a 2-case pinned source (one injected defect, one clean
    negative), one unlabeled ingested case, a fake store (case_a fresh, case_b stale),
    PACK_FILES emptied (a dev checkout's out/*.jsonl must not leak in)."""
    src = tmp_path / "cases.jsonl"
    rows = [
        _case_row(
            "case_a_defect",
            recipe={"defect_type": "record_presence", "pre_value": "x", "post_value": "y"},
            flags=["FABRICATED_CLAIM"],
        ),
        _case_row("case_b_clean", verdict="approve"),
    ]
    src.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    monkeypatch.setattr(bff, "_load_agent", lambda name, db: _Agent(src))
    monkeypatch.setattr(bff.picklist, "PACK_FILES", {})
    monkeypatch.setattr(bff, "_read_ingested_corpus", lambda: [_case_row("case_c_ingested")])
    store = _FakeStore(
        docs=[
            {"agent_id": "eval-1", "case_id": "case_a_defect"},
            {"agent_id": "eval-1", "case_id": "case_a_defect"},
            {"agent_id": "eval-1", "case_id": "case_b_clean"},
            {"agent_id": "OTHER-agent", "case_id": "case_a_defect"},  # not ours — never counted
        ],
        heads={
            ("eval-1", "case_a_defect"): {"grade_signature": "SIG-CURRENT"},
            ("eval-1", "case_b_clean"): {"grade_signature": "SIG-OLD"},
        },
    )
    monkeypatch.setattr(bff, "provenance_store_for", lambda db: store)
    monkeypatch.setattr(bff, "_current_grade_signature", lambda ag, **kw: "SIG-CURRENT")
    return lambda: bff.case_browser_endpoint(
        agent="eval-1",
        db_path=tmp_path / "config.sqlite",
        collections_db=tmp_path / "collections.sqlite",
        out_dir=tmp_path,
        workdir=tmp_path,
    )


def test_browser_lists_the_loadable_union_with_labels(browser):
    out = browser()
    by_id = {c["case_id"]: c for c in out["cases"]}
    assert list(by_id) == ["case_a_defect", "case_b_clean", "case_c_ingested"]  # load_case order

    a = by_id["case_a_defect"]
    assert a["labeled"] is True and a["defect"] == "record_presence" and a["source"] == "pinned"

    b = by_id["case_b_clean"]  # labeled with nothing planted = a first-class clean negative
    assert b["labeled"] is True and b["defect"] is None

    c = by_id["case_c_ingested"]  # BYO data: unknown ground truth, never a fake label
    assert c["labeled"] is False and c["defect"] is None and c["source"] == "ingested"


def test_browser_run_counts_and_baseline_freshness(browser):
    by_id = {c["case_id"]: c for c in browser()["cases"]}
    a, b, c = by_id["case_a_defect"], by_id["case_b_clean"], by_id["case_c_ingested"]
    assert (a["runs"], a["baseline"]) == (2, "fresh")  # head sig == current sig
    assert (b["runs"], b["baseline"]) == (1, "stale")  # graded under an older config
    assert (c["runs"], c["baseline"]) == (0, "none")  # never graded — nothing to replay


def test_current_grade_signature_threads_or_none_like_the_grade(tmp_path, monkeypatch):
    """The None-vs-{} trap: run_eval main() passes ``assignments or None`` / ``models or None``
    into run() → grade_signature embeds them RAW (only criteria/samples/temperatures get
    ``or {}``). An empty judges store must therefore hash assignments=None — hashing ``{}``
    instead would misreport every pre-authoring baseline as stale."""
    from lithrim_bench.harness import pack as pack_mod

    ws = type("W", (), {"pack": "_core"})()
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda: ws)
    monkeypatch.setattr(pack_mod, "pack_lenses", lambda pack=None: {})
    onto = tmp_path / "onto.json"
    onto.write_text(json.dumps({"flags": [{"flag": "F1"}]}))

    class _Ag:
        name = "eval-1"

        class eval_profile:  # noqa: N801
            council_config: dict = {}

        def ontology_abspath(self):
            return onto

    sig = bff._current_grade_signature(
        _Ag(), db_path=tmp_path / "config.sqlite", workdir=tmp_path, out_dir=None
    )
    expected = grade_signature(
        json.loads(onto.read_text()),
        assignments=None,
        models=None,
        council_config={},
        criteria=None,
        samples=None,
        temperatures=None,
        demo_digests={},
    )
    assert sig == expected
