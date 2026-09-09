"""ENSEMBLE-1: the model-diversity arm's per-judge table is read from the trail, never fabricated."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "ragtruth_ensemble", REPO / "examples/ragtruth/arms/ensemble.py"
)
en = importlib.util.module_from_spec(_spec)
sys.modules["ragtruth_ensemble"] = en
_spec.loader.exec_module(en)


def _vote(role, model, served, usage=None, errors=(), latency=1000):
    return {
        "judge_role": role,
        "model": model,
        "served_model": served,
        "latency_ms": latency,
        "usage": usage,
        "errors": list(errors),
    }


def test_per_judge_table_costs_each_judge_from_its_own_votes():
    grade = {
        "matrix": [{"case_id": "c1", "run_id": "r1"}, {"case_id": "c2", "run_id": "r2"}],
        "scorecard": {
            "by_judge": [
                {"judge_role": "a", "matches_gold": 2, "misses": 0, "over_flags": 0},
                {"judge_role": "b", "matches_gold": 1, "misses": 1, "over_flags": 0},
            ]
        },
    }
    blobs = {
        "r1": {
            "stage_results": {
                "semantic": {
                    "judge_votes": [
                        _vote(
                            "a",
                            "azure/gpt-4.1",
                            "gpt-4.1-2025-04-14",
                            {"input_tokens": 1_000_000, "output_tokens": 0},
                        ),
                        _vote(
                            "b",
                            "openai/Mistral-Large-3",
                            "mistral-large-3",
                            {"input_tokens": 1_000_000, "output_tokens": 1_000_000},
                        ),
                    ]
                }
            }
        },
        "r2": {
            "stage_results": {
                "semantic": {
                    "judge_votes": [
                        _vote(
                            "a",
                            "azure/gpt-4.1",
                            "gpt-4.1-2025-04-14",
                            {"input_tokens": 0, "output_tokens": 1_000_000},
                        ),
                        _vote(
                            "b",
                            "openai/Mistral-Large-3",
                            "mistral-large-3",
                            None,
                            errors=["content filter"],
                            latency=None,
                        ),
                    ]
                }
            }
        },
    }
    rows = {r["judge_role"]: r for r in en.per_judge_table(grade, blobs)}
    a, b = rows["a"], rows["b"]
    assert a["votes"] == 2 and a["errors"] == 0 and a["matches_gold"] == 2
    assert a["served_models"] == {"gpt-4.1-2025-04-14": 2} and a["latency_ms_mean"] == 1000
    gi, go = en.price_for("azure/gpt-4.1")
    assert a["usd_list"] == round(gi + go, 2) and a["usd_list_per_case"] == round((gi + go) / 2, 4)
    assert b["errors"] == 1 and b["votes_with_usage"] == 1 and b["misses"] == 1
    assert b["usd_list"] == round(2.0 + 6.0, 2) and b["priced_with"] == "2.0/6.0 per M"
    assert en.price_for("openai/Unknown-Model-X") is None


def test_v1_route_and_members_are_the_same_lens_on_three_models():
    assert (
        en.v1_route("https://res.services.ai.azure.com/")
        == "https://res.services.ai.azure.com/openai/v1"
    )
    assert (
        en.v1_route("https://res.services.ai.azure.com/openai/v1/")
        == "https://res.services.ai.azure.com/openai/v1"
    )
    roles = [m["role"] for m in en.MEMBERS]
    assert roles[0] == en.ROLE == "ragtruth_detector" and len(set(roles)) == 3
    assert {m["provider"] for m in en.MEMBERS[1:]} == {"openai_compatible"}


def test_grade_refuses_without_confirm(tmp_path):
    s = tmp_path / "slice.jsonl"
    s.write_text('{"case_id": "c1"}\n')
    out = subprocess.run(
        [
            sys.executable,
            str(REPO / "examples/ragtruth/arms/ensemble.py"),
            "grade",
            "--slice",
            str(s),
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
        env={"PATH": "/usr/bin"},
    )
    assert out.returncode != 0 and "REFUSING a paid grade of 1 cases x 3 judges" in out.stderr


def test_e2_is_the_pack_trio_on_one_model_with_k_pinned_and_lens_from_snapshot(tmp_path):
    trio = en.ARMS["e2"]
    assert [m["role"] for m in trio] == ["faithfulness_judge", "risk_judge", "policy_judge"]
    assert {(m["provider"], m["model"], m["k"]) for m in trio} == {("azure", "gpt-4.1", 1)}
    snap = tmp_path / "taxonomy_snapshot.json"
    snap.write_text(
        '{"lenses": {"risk_judge": ["UNSUPPORTED_ASSERTION", "INTERNAL_INCONSISTENCY"]}}'
    )
    assert en.lens_for("risk_judge", snap) == ["UNSUPPORTED_ASSERTION", "INTERNAL_INCONSISTENCY"]
    try:
        en.lens_for("policy_judge", snap)
    except SystemExit as exc:
        assert "no lens" in str(exc)
    else:
        raise AssertionError("a role without a lens must fail closed")
