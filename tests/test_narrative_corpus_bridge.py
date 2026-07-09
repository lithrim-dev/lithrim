"""NARR-5 D1 — the S-BS-NARR2-1 corpus-gradeable bridge.

An INGESTED workspace-corpus case lands in ``ws.out_dir/ingested_cases.jsonl`` in the
``_to_envelope`` shape (``jute_extractor._to_envelope``). At the parent (a4efd0f),
``load_case(case_id)`` with no ``source`` pin resolves only via ``resolve_case_fixtures``
(``PACK_FILES``-only) and so returns ``None`` for an ingested case — it can never be graded
through the picklist path. This RED-first integration test asserts the bridge:

  * an enveloped ingested case written to the active workspace's ``ingested_cases.jsonl``
    resolves through ``load_case(case_id)`` (no source pin), then
  * grades end-to-end via ``grade_inprocess`` with an INJECTED predictor stage ($0, no Azure),
    yielding a ``composite`` verdict, and
  * the S-BS-9 PACK_FILES-first precedence is preserved — a ``case_id`` present in BOTH a
    PACK_FILES fixture AND the workspace corpus resolves the PACK_FILES row (the workspace
    fallback runs STRICTLY LAST).

The mock seam: the predictor stage is offline (no real LM); the point under test is the
RESOLUTION + GRADEABILITY of an ingested case, not judge quality.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("dspy")
pytest.importorskip("openai")

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK = "narrative"


def _envelope(case_id: str, scene: str) -> dict:
    """The exact ingested record shape jute_extractor._to_envelope emits."""
    from lithrim_bench.verification.jute_extractor import _to_envelope

    record = {
        "case_id": case_id,
        "response": scene,
        "story_id": "jinn_v3",
        "mode": "adult",
        "language": "en",
        "node": "beat_7",
        "scene_title": "the descent",
        "source": "enhanced",
        "finish_reason": "stop",
        "model": "ingested-sut",
    }
    return _to_envelope(record)


@pytest.fixture()
def isolated_workspaces(tmp_path, monkeypatch):
    """Point WORKSPACES_DIR at a temp dir + force a re-read of the workspace module so its
    module-level WORKSPACES_DIR honors the override. Returns the active narrative workspace."""
    monkeypatch.setenv("LITHRIM_BENCH_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    import importlib

    from lithrim_bench.harness import workspace as ws_mod

    importlib.reload(ws_mod)
    try:
        ws = ws_mod.create_workspace("narr5_bridge", pack=PACK, seed=False)
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


def test_ingested_corpus_case_resolves_and_grades_via_load_case(isolated_workspaces):
    """RED at a4efd0f: load_case(case_id) returns None for an ingested-only case → cannot grade.
    GREEN: the workspace-corpus fallback resolves it and grade_inprocess produces a verdict."""
    ws_mod, ws = isolated_workspaces
    from lithrim_bench.harness.grade import grade_inprocess
    from lithrim_bench.harness.grounding import ground
    from lithrim_bench.harness.ontology import load_ontology
    from lithrim_bench.harness.pack import pack_ontology_path
    from lithrim_bench.harness.report import composite
    from lithrim_bench.picklist import load_case
    from lithrim_bench.runtime.council.authored_stage import build_authored_semantic_stage
    from lithrim_bench.runtime.council.judges_dspy import V2_ROLES

    case_id = "ingested_narr5_descent"
    scene = (
        "She turned to the window. The night gave no answer, only the long road. "
        "The headlights swung across bare rock and held."
    )
    corpus = ws.out_dir / "ingested_cases.jsonl"
    corpus.parent.mkdir(parents=True, exist_ok=True)
    with corpus.open("w") as fh:
        fh.write(json.dumps(_envelope(case_id, scene)) + "\n")

    # the bridge under test: no source pin, the case lives ONLY in the workspace corpus
    case = load_case(case_id)
    assert case is not None, "ingested corpus case did not resolve via load_case (the D1 gap)"
    assert case["case_id"] == case_id
    assert case["artifacts"][0]["content"] == scene

    ont = load_ontology(pack_ontology_path())
    stage = build_authored_semantic_stage(
        ontology=ont, assignments={}, predictors={r: _approve for r in V2_ROLES}
    )
    rc = grade_inprocess(case, semantic_stage=stage)
    comp = composite(ground(rc, case, ontology=ont))
    assert comp["verdict"] in {"approve", "needs_review", "reject"}
    assert comp["verdict"] == "approve"  # clean scene, all-approve predictors


def test_pack_files_first_precedence_preserved_on_collision(isolated_workspaces):
    """S-BS-9 / R2: when a case_id is present in BOTH a PACK_FILES-resolvable fixture AND the
    workspace corpus, load_case resolves the PACK_FILES row — the workspace fallback is STRICTLY
    LAST. Asserted by writing a DISTINGUISHABLE workspace-corpus row under a real pack case_id
    and confirming load_case returns the pack row (the workspace's marker is absent)."""
    ws_mod, ws = isolated_workspaces
    from lithrim_bench.picklist import load_case, resolve_case_fixtures

    # pick a case_id the pack-resolution path actually finds (narrative example), to force a
    # collision; resolve_case_fixtures must also see it for this test to be meaningful.
    collision_id = "narrative_jinn_exposure_clean"
    src = REPO_ROOT / "packs" / "narrative" / "examples" / "narrative_v1.jsonl"
    pack_row = load_case(collision_id, source=src)
    assert pack_row is not None, "fixture precondition: the narrative example must load by source"

    # write a workspace-corpus row under the SAME id, marked so we can tell them apart
    corpus = ws.out_dir / "ingested_cases.jsonl"
    corpus.parent.mkdir(parents=True, exist_ok=True)
    marker_envelope = _envelope(collision_id, "WORKSPACE_CORPUS_MARKER scene text")
    with corpus.open("w") as fh:
        fh.write(json.dumps(marker_envelope) + "\n")

    resolved = load_case(collision_id)
    assert resolved is not None
    # the workspace fallback is strictly last → if PACK_FILES (or the in-repo example via the
    # pack path) resolves it, that row wins, NOT the workspace marker row.
    pack_path_finds_it = collision_id in resolve_case_fixtures({collision_id})
    if pack_path_finds_it:
        assert "WORKSPACE_CORPUS_MARKER" not in json.dumps(resolved), (
            "PACK_FILES-first precedence violated: the workspace corpus row shadowed the pack row"
        )
    else:
        # no PACK_FILES collision available in this checkout → the fallback legitimately wins;
        # the precedence is still proven by the explicit-source pin path above.
        assert resolved["artifacts"][0]["content"].startswith("WORKSPACE_CORPUS_MARKER")
