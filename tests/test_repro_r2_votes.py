"""REPRO-1 R2c — the per-sample K-split is READABLE: each judge vote carries its raw sampled
scores (``scores_raw`` — decision-derived floats: 0.0 reject / 0.5 needs_review / 1.0 approve),
so a "sampled 5 times: 3 BLOCK / 2 PASS" split is a pure derivation on the read surface.

The gap: ``sampling.scores_raw`` was captured on the seam dict (authored_stage) but dropped at
``_judge_votes_from_models`` — the stored vote kept only the aggregate variance + k, so the
stability evidence (the thesis's within-call verdict split) was invisible to every consumer.

Also pins: the roster endpoint accepts a MULTI-role subset (the N-clone council the shell's
custom mode saves). $0/offline.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("openai")  # `stages` -> compliance_council imports openai at module load

from lithrim_bench.runtime.pipeline.stages import _judge_votes_from_models  # noqa: E402

_SEAM = [
    {
        "model": "reviewer_gpt41",
        "decision": "approve",
        "confidence": 0.71,
        "findings": [],
        "llm_model": "gpt-4.1",
        "sampling": {
            "score_mean": 0.6,
            "score_variance": 0.24,
            "scores_raw": [0.0, 0.0, 1.0, 1.0, 1.0],
            "k": 5,
        },
    },
    {"model": "reviewer_sonnet", "decision": "reject", "confidence": None, "findings": []},
]


def test_votes_carry_the_raw_sampled_scores():
    votes = _judge_votes_from_models(_SEAM)
    v = votes[0]
    assert v.scores_raw == [0.0, 0.0, 1.0, 1.0, 1.0]
    assert v.k == 5 and v.variance == 0.24


def test_votes_carry_BOTH_confidence_channels_side_by_side():
    """R2c dual-confidence: the logprob `confidence` must NOT overwrite the reviewer's own
    self-reported decision aggregate. The sampled `score_mean` rides `confidence_self`, kept
    DISTINCT from the logprob-derived `confidence` — both readable on one vote."""
    votes = _judge_votes_from_models(_SEAM)
    v = votes[0]
    assert v.confidence == 0.71  # the logprob channel is untouched
    assert v.confidence_self == 0.6  # the self-report (sampled decision mean) is preserved
    assert v.confidence != v.confidence_self  # two channels, not one clobbering the other


def test_unsampled_vote_has_none_confidence_self_never_fabricated():
    votes = _judge_votes_from_models(_SEAM)
    assert votes[1].confidence_self is None


def test_unsampled_vote_has_none_scores_raw_never_a_fabricated_list():
    votes = _judge_votes_from_models(_SEAM)
    assert votes[1].scores_raw is None
    assert votes[1].k is None


def test_council_view_projects_scores_raw_to_the_read_surface():
    pytest.importorskip("fastapi", reason="needs the [bff] extra")
    _BFF = REPO_ROOT / "apps" / "bff"
    if str(_BFF) not in sys.path:
        sys.path.insert(0, str(_BFF))
    import app as bff

    record = {
        "result": {
            "semantic": {
                "judge_votes": [
                    {
                        "judge_role": "reviewer_gpt41", "vote": "PASS", "confidence": 0.7,
                        "confidence_self": 0.6,
                        "model": "gpt-4.1", "reason": "r", "variance": 0.24, "k": 5,
                        "scores_raw": [0.0, 0.0, 1.0, 1.0, 1.0],
                    }
                ]
            }
        }
    }
    view = bff._council_view(record)
    assert view["votes"][0]["scores_raw"] == [0.0, 0.0, 1.0, 1.0, 1.0]
    # R2c dual-confidence: BOTH channels reach the read surface, side by side.
    assert view["votes"][0]["confidence"] == 0.7
    assert view["votes"][0]["confidence_self"] == 0.6


def test_roster_endpoint_accepts_a_multi_role_subset(tmp_path, monkeypatch):
    """The N-clone council: a 2-role roster persists and reads back (the shell's custom mode)."""
    pytest.importorskip("fastapi", reason="needs the [bff] extra")
    _BFF = REPO_ROOT / "apps" / "bff"
    if str(_BFF) not in sys.path:
        sys.path.insert(0, str(_BFF))
    import app as bff
    from fastapi.testclient import TestClient

    from lithrim_bench.harness.config import save_agent
    from tests._house_fixture import house_agent

    db = tmp_path / "config.sqlite"
    save_agent(house_agent(name="r2_roster"), db_path=db)
    monkeypatch.setattr(
        bff.workspace,
        "get_active_workspace",
        lambda: bff.workspace.Workspace(name="default", pack=bff.workspace.DEFAULT_PACK),
    )
    bff.app.dependency_overrides[bff.get_config_db] = lambda: db
    try:
        client = TestClient(bff.app)
        panel = client.get("/v1/council/roster", params={"agent": "r2_roster"}).json()["panel"]
        assert len(panel) >= 2, panel
        pair = panel[:2]
        resp = client.post(
            "/v1/council/roster", json={"agent": "r2_roster", "roster": pair}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["reviewer_roster"] == pair
        got = client.get("/v1/council/roster", params={"agent": "r2_roster"}).json()
        assert got["reviewer_roster"] == pair
    finally:
        bff.app.dependency_overrides.clear()
