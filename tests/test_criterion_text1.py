"""CRITERION-TEXT-1: the criterion TEXT — ``when_to_use`` / ``when_NOT_to_use`` /
``definition`` — is authorable, not just tier/gradeable.

The P0 this closes: ``when_to_use`` is the one ontology field that renders into a judge's
prompt (judge_assignment.py builds the AUTHORED REFINEMENT lens line from it), yet no
authoring surface could touch it — author_flag edited only tier/gradeable, CriterionBuilder
never collected it, FlagEditor never showed it. The calibration loop ("reword the criterion
→ re-run → compare") dead-ended at the reword. SIGNATURE-1 already hashes the ontology, so
an edited text honestly stales prior heads; this adds the sanctioned editor in front of it.

Hermetic — the uap5c pattern: tool handlers against the real (frozen) BFF ops over a tmp
config DB. Requires the [bff] extra.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.config import save_agent

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi/httpx)")
from fastapi.testclient import TestClient  # noqa: E402

from tests._house_fixture import house_agent  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402
from agent.tools import (  # noqa: E402
    AUTHOR_CRITERION_SCHEMA,
    AUTHOR_FLAG_SCHEMA,
    author_criterion_handler,
    author_flag_handler,
)

AGENT = "crit_text1_test"


@pytest.fixture
def env(tmp_path, monkeypatch):
    db = tmp_path / "bench_config.sqlite"
    save_agent(house_agent(name=AGENT), db_path=db)
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
    ctx = bff._build_tool_context(
        req_agent=AGENT,
        db_path=db,
        out_dir=tmp_path / "out",
        workdir=tmp_path / "ont",
        collections_db=tmp_path / "coll.sqlite",
        actor=bff.Actor(type="system", id="test-sme"),
        x_actor=None,
    )
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db
    try:
        yield ctx, TestClient(bff.app), tmp_path / "ont" / f"{AGENT}.json"
    finally:
        bff.app.dependency_overrides.clear()


def _flag(working_copy: Path, code: str) -> dict:
    ontology = json.loads(working_copy.read_text())
    return next(f for f in ontology["flags"] if f["flag"] == code)


def test_author_flag_edits_the_criterion_text(env):
    """The chat tool rewords a criterion: when_to_use / when_NOT_to_use / definition land in
    the audited working copy; tier/gradeable are preserved untouched."""
    ctx, client, working_copy = env
    res = asyncio.run(
        author_flag_handler(
            ctx,
            {
                "flag_code": "FABRICATED_CLAIM",
                "definition": "A figure or rule the source never states.",
                "when_to_use": "1) The response cites a NUMBER absent from the source.",
                "when_NOT_to_use": "The figure is a unit conversion of a stated value.",
                "rationale": "sharpen the lens after the over-fire review",
            },
        )
    )
    assert not res.get("is_error"), res
    f = _flag(working_copy, "FABRICATED_CLAIM")
    assert f["when_to_use"] == "1) The response cites a NUMBER absent from the source."
    assert f["when_NOT_to_use"] == "The figure is a unit conversion of a stated value."
    assert f["definition"] == "A figure or rule the source never states."
    assert f["tier"] == "TIER_1" and f["gradeable"] is True  # untouched facets preserved
    recs = client.get("/v1/audit", params={"target_type": "ontology"}).json()["records"]
    assert len(recs) == 1 and recs[0]["action"] == "edit"


def test_text_only_edit_leaves_other_flags_and_facets_alone(env):
    """An omitted field is UNTOUCHED (None ≠ clear); sibling flags are byte-identical."""
    ctx, _client, working_copy = env
    before = json.loads(Path(house_agent().eval_profile.ontology_path).read_text())
    res = asyncio.run(
        author_flag_handler(
            ctx, {"flag_code": "FABRICATED_CLAIM", "when_to_use": "reworded lens only"}
        )
    )
    assert not res.get("is_error"), res
    f = _flag(working_copy, "FABRICATED_CLAIM")
    f_before = next(x for x in before["flags"] if x["flag"] == "FABRICATED_CLAIM")
    assert f["when_to_use"] == "reworded lens only"
    assert f["when_NOT_to_use"] == f_before["when_NOT_to_use"]  # omitted → untouched
    assert f["definition"] == f_before["definition"]
    assert _flag(working_copy, "UNSUPPORTED_ASSERTION") == next(
        x for x in before["flags"] if x["flag"] == "UNSUPPORTED_ASSERTION"
    )


def test_the_edited_lens_reaches_the_judge_prompt_input(env):
    """The bridge is honest end-to-end: the working copy round-trips through the harness
    Ontology model, so judge_assignment's ``fd.when_to_use`` read sees the reworded text."""
    ctx, _client, working_copy = env
    asyncio.run(
        author_flag_handler(
            ctx, {"flag_code": "FABRICATED_CLAIM", "when_to_use": "THE REWORDED LENS"}
        )
    )
    from lithrim_bench.harness import ontology as ont_mod

    ont = ont_mod.from_dict(json.loads(working_copy.read_text()))
    assert ont.flag("FABRICATED_CLAIM").when_to_use == "THE REWORDED LENS"


def test_author_flag_schema_carries_the_text_fields():
    """The agent can PASS the reworded text (schema-gated at the SDK-MCP boundary)."""
    for key in ("definition", "when_to_use", "when_NOT_to_use"):
        assert AUTHOR_FLAG_SCHEMA.get(key) is str, key


def test_author_criterion_seeds_the_drafted_text_into_the_card(env):
    """The agent DRAFTS the criterion text conversationally; the card opens pre-seeded and
    the human's Save stays the sole write (emit-only — no ontology touch here)."""
    ctx, client, working_copy = env
    for key in ("definition", "when_to_use", "when_NOT_to_use"):
        assert AUTHOR_CRITERION_SCHEMA.get(key) is str, key
    res = asyncio.run(
        author_criterion_handler(
            ctx,
            {
                "code": "EVERY_DOSE_IN_SOAP",
                "tier": "TIER_2",
                "owner_role": "faithfulness_judge",
                "definition": "Every dose in the transcript appears in the SOAP.",
                "when_to_use": "1) A dose stated in the transcript is absent from the note.",
                "when_NOT_to_use": "The dose appears with different but equivalent units.",
            },
        )
    )
    assert not res.get("is_error"), res
    part = ctx.parts[-1]
    assert part["type"] == "tool-criterion_builder"
    out = part["output"]
    assert out["when_to_use"] == "1) A dose stated in the transcript is absent from the note."
    assert out["when_NOT_to_use"] == "The dose appears with different but equivalent units."
    assert out["definition"] == "Every dose in the transcript appears in the SOAP."
    assert not working_copy.exists()  # emit-only: surfacing the card writes NOTHING
    recs = client.get("/v1/audit", params={"target_type": "ontology"}).json()["records"]
    assert recs == []
