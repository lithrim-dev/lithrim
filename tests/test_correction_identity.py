"""CORRECTION-IDENTITY-1: every correction row names its case, agent, run, and write time.

Observed 2026-09-09: the floor-correction rows for ragtruth_5827 (a clean case value-grounding/1
blocked on a mis-read "3") could not be selected from out/ws0/corrections.ndjson because rows
carried no case id and no timestamp. A versioned contract fix is only demonstrable if the
before row (v1 enforced) and the after row (v2 pass) can be put side by side."""

from __future__ import annotations

from lithrim_bench.harness.correction import build_floor_correction
from lithrim_bench.harness.grounding import ground
from tests.test_ws4a import _COUNCIL_PASS, _DEFECT_CASE, _floor_ontology, _ReplayHttp


def _floor_block():
    ont = _floor_ontology()
    g = ground(_COUNCIL_PASS, _DEFECT_CASE, ontology=ont, http_client=_ReplayHttp())
    return ont, g


def test_floor_correction_carries_case_agent_run_and_ts():
    ont, g = _floor_block()
    rec = build_floor_correction(
        floor_block=g.floor_blocks[0],
        result=_COUNCIL_PASS,
        composite_before="PASS",
        composite_after=g.verdict,
        ontology=ont,
        case_id="ragtruth_5827",
        agent_id="ws0_default",
        pipeline_run_id="run-1",
    )
    assert (rec["case_id"], rec["agent_id"], rec["pipeline_run_id"]) == (
        "ragtruth_5827",
        "ws0_default",
        "run-1",
    )
    assert rec["ts"].endswith("+00:00") and rec["contract_version"]


def test_offline_builders_keep_the_keys_but_never_fabricate_identity():
    ont, g = _floor_block()
    rec = build_floor_correction(
        floor_block=g.floor_blocks[0],
        result=_COUNCIL_PASS,
        composite_before="PASS",
        composite_after=g.verdict,
        ontology=ont,
    )
    assert rec["case_id"] is None and rec["agent_id"] is None and rec["pipeline_run_id"] is None
    assert "ts" in rec
