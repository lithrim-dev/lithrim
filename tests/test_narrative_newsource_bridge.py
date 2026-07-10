"""NARR-7 (P-GEN) A5 (D1 bridge) — a GitHub-ingested NEW-source case is gradeable.

The "eval anything" generality reaches the grade path: a GitHub comment ingested through
``_to_envelope`` (NOT a StoryWorld scene) lands in ``ws.out_dir/ingested_cases.jsonl`` and
resolves via ``load_case(case_id)`` (the S-BS-NARR2-1 / NARR-5 workspace-corpus fallback), then
grades end-to-end via ``grade_inprocess`` with an INJECTED predictor stage ($0, no Azure). This
mirrors the NARR-5 ``test_narrative_corpus_bridge`` / NARR-6 batch-bridge pattern, proving a
genuinely non-clinical, non-StoryWorld shape is gradeable by ``case_id``.

$0/offline: the predictor stage is offline (no real LM); the point under test is the RESOLUTION
+ GRADEABILITY of an arbitrary-source ingested case.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("dspy")
pytest.importorskip("openai")

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK = "narrative"
GH_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "narrative" / "github_newsource_sample.json"


def _github_envelope(case_id: str, body: str, issue_title: str) -> dict:
    """The exact ingested record shape jute_extractor._to_envelope emits for a GitHub comment.
    A GitHub record has NO StoryWorld fields (story_id/mode/language) — only case_id + response
    + source are populated; the envelope must still resolve + grade."""
    from lithrim_bench.verification.jute_extractor import _to_envelope

    record = {
        "case_id": case_id,
        "response": body,
        "scene_title": issue_title,
        "source": "github",
    }
    return _to_envelope(record)


@pytest.fixture()
def isolated_workspaces(tmp_path, monkeypatch):
    monkeypatch.setenv("LITHRIM_BENCH_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    import importlib

    from lithrim_bench.harness import workspace as ws_mod

    importlib.reload(ws_mod)
    try:
        ws = ws_mod.create_workspace("narr7_bridge", pack=PACK, seed=False)
        ws_mod.set_active_workspace(ws.name)
        yield ws_mod, ws
    finally:
        # S-REL-24 (REL-5e): un-patch the env BEFORE the reload — workspace.py binds
        # WORKSPACES_DIR at import, and monkeypatch's env restore runs AFTER this finally,
        # so reloading under the patched env froze the tmp dir (and its .active workspace)
        # into the module for the REST OF THE SESSION (the gate0 bff-victim leak).
        monkeypatch.delenv("LITHRIM_BENCH_WORKSPACES_DIR", raising=False)
        importlib.reload(ws_mod)


def _approve(*, role_key_questions="", **_kw):
    return {"decision": "approve", "findings": []}


def test_github_ingested_case_resolves_and_grades_via_load_case(isolated_workspaces):
    """RED at parent before the new-source fixture/path lands. GREEN: a GitHub comment ingested
    through _to_envelope resolves via load_case(case_id) and grade_inprocess produces a verdict —
    a NON-clinical, NON-StoryWorld case gradeable by case_id (the generality)."""
    ws_mod, ws = isolated_workspaces
    from lithrim_bench.harness.grade import grade_inprocess
    from lithrim_bench.harness.grounding import ground
    from lithrim_bench.harness.ontology import load_ontology
    from lithrim_bench.harness.pack import pack_ontology_path
    from lithrim_bench.harness.report import composite
    from lithrim_bench.picklist import load_case
    from lithrim_bench.runtime.council.authored_stage import build_authored_semantic_stage
    from lithrim_bench.runtime.council.judges_dspy import V2_ROLES

    dump = json.loads(GH_FIXTURE.read_text())
    cm = dump["comments"][0]
    issue = {i["number"]: i for i in dump["issues"]}[cm["issue_number"]]
    case_id = f"gh-{cm['id']}"

    corpus = ws.out_dir / "ingested_cases.jsonl"
    corpus.parent.mkdir(parents=True, exist_ok=True)
    with corpus.open("w") as fh:
        fh.write(json.dumps(_github_envelope(case_id, cm["body"], issue["title"])) + "\n")

    case = load_case(case_id)
    assert case is not None, "the GitHub-ingested case did not resolve via load_case (the D1 gap)"
    assert case["case_id"] == case_id
    assert case["artifacts"][0]["content"] == cm["body"]

    ont = load_ontology(pack_ontology_path())
    stage = build_authored_semantic_stage(
        ontology=ont, assignments={}, predictors={r: _approve for r in V2_ROLES}
    )
    rc = grade_inprocess(case, semantic_stage=stage)
    comp = composite(ground(rc, case, ontology=ont))
    assert comp["verdict"] in {"approve", "needs_review", "reject"}
    assert comp["verdict"] == "approve"  # clean comment, all-approve predictors
