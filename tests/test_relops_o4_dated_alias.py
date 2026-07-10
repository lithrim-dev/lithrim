"""REL-OPS-1 O4 — the dated-model-alias policy, checked at judge BIND time.

SPEC (SPEC_RELIABILITY_PROGRAM.md O4): "Warn (or refuse, per config) when a judge binds
a floating alias instead of a dated snapshot; record which was used. One check at bind
time." Honesty constraint: O4 observes/records/gates ABOVE the frozen seam — it never
touches consensus; the moat stays byte-frozen.

Seam: ``build_judge_lm``/``build_trio`` live in the FROZEN ``judges_dspy.py``, so the
check binds in ``authored_stage.build_authored_evaluator`` — the non-frozen construction
site where VOTE-MODEL-1 already stamped each judge's resolved model as ``llm_model``.
The classifier + registry are pure/stdlib (``harness/model_policy.py``); the recorded
bindings ride ``plugins.provenance_snapshot()`` → ``PipelineProvenance.model_bindings``
(the TOOL-1/D5 additive-provenance pattern).
"""

from __future__ import annotations

import logging

import pytest

from lithrim_bench.harness import model_policy as MP

REFUSE_ENV = "LITHRIM_BENCH_REQUIRE_DATED_MODELS"


@pytest.fixture(autouse=True)
def _clean_policy_state(monkeypatch):
    monkeypatch.delenv(REFUSE_ENV, raising=False)
    MP._reset_model_bindings()
    yield
    MP._reset_model_bindings()


# ─────────────────────────── classifier truth table (pure) ───────────────────────────


@pytest.mark.parametrize(
    ("model_id", "dated"),
    [
        # dated, openai-style (dashed ISO date suffix)
        ("gpt-4o-2024-08-06", True),
        ("openai/gpt-4.1-2025-04-14", True),
        # dated, anthropic-style (compact YYYYMMDD suffix)
        ("claude-3-5-sonnet-20241022", True),
        ("anthropic/claude-sonnet-4-20250514", True),
        # bare aliases float
        ("gpt-4o", False),
        ("azure/council-gpt4o", False),
        ("byo-claude", False),
        # -latest is explicitly floating, even with a date elsewhere
        ("claude-3-5-sonnet-latest", False),
        ("gpt-4o-2024-08-06-latest", False),
        # weird-but-dated: date token embedded, not terminal
        ("azure/my-council-deploy-20251001-eu2", True),
        ("acme-lab-2026-01-31-preview", True),
        # digit runs that are NOT dates do not count
        ("llama-3-70b-instruct", False),
        ("gpt-4-32k", False),
    ],
)
def test_classifier_truth_table(model_id, dated):
    assert MP.is_dated_model_id(model_id) is dated


def test_classifier_empty_is_floating():
    assert MP.is_dated_model_id("") is False
    assert MP.is_dated_model_id("   ") is False


# ─────────────────────────── warn path (default policy) ───────────────────────────


def test_warn_path_records_bindings_and_warns(caplog):
    """Default (env unset): a floating binding WARNS and every binding is RECORDED
    role→model+dated into the module registry the provenance snapshot reads."""
    with caplog.at_level(logging.WARNING, logger="lithrim_bench.harness.model_policy"):
        records = MP.check_model_bindings(
            {
                "risk_judge": "azure/council-gpt4o",
                "policy_judge": "openai/gpt-4o-2024-08-06",
            }
        )
    by_role = {r["role"]: r for r in records}
    assert by_role["risk_judge"] == {
        "role": "risk_judge",
        "model": "azure/council-gpt4o",
        "dated": False,
    }
    assert by_role["policy_judge"] == {
        "role": "policy_judge",
        "model": "openai/gpt-4o-2024-08-06",
        "dated": True,
    }
    warned = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("risk_judge" in m and "azure/council-gpt4o" in m for m in warned)
    assert not any("policy_judge" in m for m in warned)  # dated binding never warns
    assert MP.last_model_bindings() == records


def test_all_dated_bindings_are_silent(caplog):
    with caplog.at_level(logging.WARNING, logger="lithrim_bench.harness.model_policy"):
        MP.check_model_bindings({"risk_judge": "gpt-4o-2024-08-06"})
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_unbound_lm_is_recorded_dated_none_and_never_warns(caplog):
    """The offline ``predictors=`` path binds NO LM (``llm_model is None``) — recorded
    honestly as ``dated: None``, never warned, never refused."""
    with caplog.at_level(logging.WARNING, logger="lithrim_bench.harness.model_policy"):
        records = MP.check_model_bindings({"risk_judge": None})
    assert records == [{"role": "risk_judge", "model": None, "dated": None}]
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


# ─────────────────────────── refuse path (env switch) ───────────────────────────


def test_refuse_mode_raises_naming_role_and_alias(monkeypatch):
    monkeypatch.setenv(REFUSE_ENV, "1")
    with pytest.raises(ValueError) as exc:
        MP.check_model_bindings(
            {"risk_judge": "azure/council-gpt4o", "policy_judge": "gpt-4o-2024-08-06"}
        )
    msg = str(exc.value)
    assert "risk_judge" in msg and "azure/council-gpt4o" in msg
    assert "policy_judge" not in msg  # the dated binding is not the offender


def test_refuse_mode_passes_when_all_dated(monkeypatch):
    monkeypatch.setenv(REFUSE_ENV, "1")
    records = MP.check_model_bindings({"risk_judge": "claude-3-5-sonnet-20241022"})
    assert records[0]["dated"] is True


def test_refuse_mode_ignores_unbound_offline_judges(monkeypatch):
    monkeypatch.setenv(REFUSE_ENV, "1")
    MP.check_model_bindings({"risk_judge": None})  # must not raise


def test_default_env_is_warn_not_refuse():
    """Env unset → warn-only: a floating binding NEVER raises (grading byte-identical)."""
    MP.check_model_bindings({"risk_judge": "gpt-4o"})  # must not raise


# ─────────────────────────── bind-time wiring (authored stage) ───────────────────────────


class _FakeJudge:
    def __init__(self, role, llm_model):
        self.role = role
        self.llm_model = llm_model
        self.role_prompt = ""


def _patch_trio(monkeypatch, bindings):
    from lithrim_bench.runtime.council import judges_dspy

    monkeypatch.setattr(
        judges_dspy,
        "build_trio",
        lambda **kw: [_FakeJudge(r, m) for r, m in bindings.items()],
    )


def test_bind_time_check_runs_at_evaluator_construction(monkeypatch, caplog):
    """The O4 check fires when the authored evaluator is BUILT (bind time), recording
    each role's resolved ``llm_model`` — before any grade runs."""
    from lithrim_bench.runtime.council.authored_stage import build_authored_evaluator

    _patch_trio(
        monkeypatch,
        {"risk_judge": "azure/council-gpt4o", "policy_judge": "openai/gpt-4o-2024-08-06"},
    )
    with caplog.at_level(logging.WARNING, logger="lithrim_bench.harness.model_policy"):
        build_authored_evaluator(
            ontology=None, assignments=None, council=object(), apply_gate=False
        )
    recorded = {r["role"]: r for r in MP.last_model_bindings()}
    assert recorded["risk_judge"]["dated"] is False
    assert recorded["policy_judge"]["dated"] is True
    warned = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("risk_judge" in m and "azure/council-gpt4o" in m for m in warned)


def test_bind_time_refuse_raises_before_any_grade(monkeypatch):
    from lithrim_bench.runtime.council.authored_stage import build_authored_evaluator

    monkeypatch.setenv(REFUSE_ENV, "1")
    _patch_trio(monkeypatch, {"risk_judge": "azure/council-gpt4o"})
    with pytest.raises(ValueError, match="risk_judge"):
        build_authored_evaluator(
            ontology=None, assignments=None, council=object(), apply_gate=False
        )


def test_offline_predictor_path_still_constructs_under_refuse(monkeypatch):
    """The $0 offline path (predictors= → llm_model None) must keep working even under
    refuse mode — nothing was bound, so there is nothing to pin."""
    from lithrim_bench.runtime.council.authored_stage import build_authored_evaluator

    monkeypatch.setenv(REFUSE_ENV, "1")
    _patch_trio(monkeypatch, {"risk_judge": None, "policy_judge": None})
    build_authored_evaluator(ontology=None, assignments=None, council=object(), apply_gate=False)
    assert all(r["dated"] is None for r in MP.last_model_bindings())


# ─────────────────────────── provenance (the TOOL-1/D5 pattern) ───────────────────────────


def test_provenance_snapshot_carries_model_bindings(monkeypatch):
    # Pinned to the in-repo neutral ``_core`` pack: the external healthcare pack.json
    # currently fails PackManifest validation (the pre-existing ``seed_agents``
    # extra_forbidden reconciliation debt — it fails the untouched A3 tests too),
    # and O4 is pack-independent. ``active_pack()`` reads env per call.
    from lithrim_bench.harness import plugins as P

    monkeypatch.setenv("LITHRIM_BENCH_PACK", "_core")
    MP.check_model_bindings({"risk_judge": "gpt-4o-2024-08-06"})
    snap = P.provenance_snapshot()
    assert snap["model_bindings"] == [
        {"role": "risk_judge", "model": "gpt-4o-2024-08-06", "dated": True}
    ]


def test_provenance_snapshot_model_bindings_none_when_no_check_ran(monkeypatch):
    from lithrim_bench.harness import plugins as P

    monkeypatch.setenv("LITHRIM_BENCH_PACK", "_core")
    snap = P.provenance_snapshot()
    assert snap["model_bindings"] is None


def test_pipeline_provenance_field_round_trips_and_is_default_safe():
    """The additive ``model_bindings`` field on PipelineProvenance persists via model_dump
    and older docs (no key) re-parse cleanly — the A3/D5 additive-field precedent."""
    from datetime import datetime, timezone

    from lithrim_bench.runtime.pipeline.models import PipelineProvenance

    prov = PipelineProvenance(
        pipeline_run_id="t",
        org_id="o",
        timestamp=datetime.now(timezone.utc),
        request_hash="h",
        stages_executed=[],
        model_bindings=[{"role": "risk_judge", "model": "gpt-4o-2024-08-06", "dated": True}],
    )
    doc = prov.model_dump(mode="json")
    assert doc["model_bindings"][0]["dated"] is True
    old = {
        "pipeline_run_id": "x",
        "org_id": "o",
        "timestamp": "2026-01-01T00:00:00Z",
        "request_hash": "h",
        "stages_executed": [],
    }
    assert PipelineProvenance.model_validate(old).model_bindings is None


def test_orchestrator_threads_model_bindings_into_provenance():
    """The orchestrator passes the snapshot's model_bindings into PipelineProvenance
    (source-level pin, the cost-gated-live-grade posture of the A3 test)."""
    import inspect

    from lithrim_bench.runtime.pipeline import orchestrator

    src = inspect.getsource(orchestrator)
    assert 'model_bindings=_plugin_snapshot.get("model_bindings")' in src
