"""A replayed run is stamped with the time it ran, not its baseline's time.

Observed 2026-09-09: a $0 replay of the committed `_core` baseline landed in the run trail
with the baseline's June `timestamp`, so `GET /v1/runs` / the run audit dated a run made
today three months earlier. The identity re-stamp (`provenance_to_result` with a minted
`pipeline_run_id`) is the single place a replay's identity is assembled; it must mint the
timestamp too. Rehydrate (no minted id) keeps the blob verbatim."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from lithrim_bench.harness.replay import provenance_to_result

_BASELINE_TS = "2026-06-13T04:43:08.605532Z"


def _blob() -> dict:
    return {
        "pipeline_run_id": "baseline-run",
        "timestamp": _BASELINE_TS,
        "verdict": "PASS",
        "gate_decision": "allow",
        "findings": [],
        "stage_results": {},
    }


def test_replay_identity_mints_a_fresh_timestamp():
    blob = _blob()
    result = provenance_to_result(blob, pipeline_run_id="fresh-run", replay_of="baseline-run")
    prov = result["provenance"]
    assert prov["pipeline_run_id"] == "fresh-run" and prov["replay_of"] == "baseline-run"
    assert prov["timestamp"] != _BASELINE_TS
    stamped = datetime.strptime(prov["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(
        tzinfo=timezone.utc
    )
    assert datetime.now(timezone.utc) - stamped < timedelta(minutes=1)
    assert blob["timestamp"] == _BASELINE_TS, "the baseline blob must stay byte-unchanged"


def test_rehydrate_without_a_minted_id_keeps_the_stored_timestamp():
    result = provenance_to_result(_blob())
    assert result["provenance"]["timestamp"] == _BASELINE_TS
