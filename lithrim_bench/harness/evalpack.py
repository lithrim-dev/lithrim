"""The thin eval-pack — a reusable, frozen artifact of an eval run.

An eval-pack is the second flywheel artifact (the corpus is the first): given a set
of config :class:`~lithrim_bench.harness.config.Agent` eval-profiles, it runs each
through the canonical ``run_eval.run`` core and freezes a slim, path-free,
round-trippable record: ``{pack_id, cases:[{case_id, expected}],
outcomes:[{grounded outcome + correction provenance}]}``. The frozen pack is JSON —
``dump_pack`` → ``load_pack`` is an identity round-trip (A2).

The outcome's ``corrections`` field is the ``corpus-row/1`` projection of that run's
correction records (:mod:`lithrim_bench.harness.corpus`), so a pack carries its own
flywheel provenance.

THIN-SLICE LIMITATION (WS-4a, surfaced not hidden): the replay grade path needs a
captured baseline per case, and WS-4a ships exactly ONE (the WS-0 scribe case). So a
replay-built pack is genuinely one case — that fully exercises the build→load→freeze
*mechanism*, which is what A2 tests. Multi-case baselines + a floor-apply replay
capture (S-BS-13) are WS-4b; this builder is N-agent-general by construction so that
lands without a rewrite.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from lithrim_bench.harness import corpus
from lithrim_bench.harness.config import Agent

EVALPACK_SCHEMA_VERSION = "evalpack/1"

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = REPO_ROOT / "scripts"


def _run_core():
    """Import the canonical ``run_eval.run`` core (the same one run_ws0 delegates to).

    ``scripts/`` is not a package; run_ws0.py establishes the precedent of putting it
    on ``sys.path`` and importing by module name. Done lazily so importing this module
    never pulls the script unless a pack is actually built.
    """
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    import run_eval  # noqa: PLC0415

    return run_eval.run


def _outcome(record: dict[str, Any]) -> dict[str, Any]:
    """Slim, path-free outcome (grounded verdict + correction provenance) from a run record."""
    cid = record["case_id"]
    comp = record["composite"]
    grounded = record["grounded"]
    # UAP-3 R6: the addressable run id (round-trips to /v1/runs/{id}/audit). Lives on
    # the graded PipelineResult provenance; None when the path carries none.
    run_id = ((record.get("result") or {}).get("provenance") or {}).get("pipeline_run_id")
    return {
        "case_id": cid,
        "pipeline_run_id": run_id,
        "verdict": comp["verdict"],
        "stage_verdict": comp["stage_verdict"],
        "original_verdict": grounded["original_verdict"],
        "score": comp["score"],
        "active_findings": comp["active_findings"],
        "grounded_adjustments": comp["grounded_adjustments"],
        "floor_adjustments": comp["floor_adjustments"],
        "corrections": corpus.build_corpus(record["corrections"], case_id=cid),
    }


def _case_entry(record: dict[str, Any]) -> dict[str, Any]:
    prov = record["provenance"]
    return {
        "case_id": record["case_id"],
        "expected": {
            "compliance_verdict": prov["expected_compliance_verdict"],
            "safety_flags": prov["expected_safety_flags"],
        },
    }


def build_pack(
    pack_id: str,
    agents: list[Agent],
    *,
    live: bool = False,
    in_process: bool = False,
    models: dict[str, str] | None = None,
    roles: list[str] | None = None,
    assignments: dict[str, Any] | None = None,
    out_dir: str | Path | None = None,
    collections_db: str | Path | None = None,
    pack_version: str = "1",
    threshold: float = 96.0,
    judge_set: dict[str, Any] | None = None,
    expected_locked: bool = True,
    grade_fn: Any = None,
) -> dict[str, Any]:
    """Run each agent through ``run_eval.run`` and freeze a thin eval-pack.

    ``live`` is forwarded to ``run`` (default replay, $0). ``in_process`` (DOGFOOD-1 D3)
    runs the in-process v2 council per case — a MULTI-CASE pack with no captured baseline
    (PAID Azure unless every leg is BYO-Claude). ``models``/``roles``/``assignments`` (the
    judge set) are forwarded to ``run`` so the whole pack grades under one judge set; the
    SAME assignments across sets keep the model-mix contrast apples-to-apples (the gate
    runs the authored trio + withstands-gate uniformly). ``out_dir`` is where the per-case
    persist artifacts land (pass a tmp dir in tests). ``collections_db`` is forwarded so
    each run's provenance persists to the caller's run-history DB (UAP-3 R6 — the batch run
    ids show up in ``GET /v1/runs``).

    The returned pack is JSON-round-trippable (no absolute paths, no raw baseline blob);
    each outcome carries its ``pipeline_run_id`` (the batch → run-history link). The
    manifest carries the LOCKED acceptance criteria the CI/CD gate reads:
    ``pack_version``, ``threshold`` (min reliability %), ``judge_set`` (the resolved set
    dict — provenance for which council graded), and ``expected_locked`` (the per-case
    ``expected`` block is the frozen gold the gate compares against).
    """
    # ``grade_fn`` (default the canonical ``run_eval.run``) lets a caller inject the grade — the
    # BFF passes a PACK-BOUND SUBPROCESS grader for a non-_core workspace, since the in-process
    # core lacks that pack's grounding executors. Same record shape either way, so the pack
    # assembly below is unchanged. Default None => byte-identical.
    run = grade_fn or _run_core()
    cases: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for agent in agents:
        record = run(
            agent,
            live=live,
            in_process=in_process,
            models=models,
            roles=roles,
            assignments=assignments,
            out_dir=out_dir,
            collections_db=collections_db,
        )
        cases.append(_case_entry(record))
        outcomes.append(_outcome(record))
    return {
        "schema_version": EVALPACK_SCHEMA_VERSION,
        "pack_id": pack_id,
        "pack_version": pack_version,
        "threshold": threshold,
        "judge_set": judge_set,
        "expected_locked": expected_locked,
        "cases": cases,
        "outcomes": outcomes,
    }


def dump_pack(pack: dict[str, Any], path: str | Path) -> str:
    """Freeze a pack to JSON (canonical sort-keys). Returns the path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(pack, indent=2, sort_keys=True))
    return str(p)


def load_pack(path: str | Path) -> dict[str, Any]:
    """Load a frozen pack back (the inverse of :func:`dump_pack`)."""
    return json.loads(Path(path).read_text())
