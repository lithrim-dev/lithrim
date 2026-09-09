"""Acceptance tests for the RAGTruth council-batch driver (offline; a fake BFF, no network, no keys)."""

import json

import pytest

from repro.ragtruth import council_batch as cb

GOLD_ROW = {
    "case_id": "x",
    "artifacts": [{"content": "a"}],
    "transcript": "t",
    "expected_safety_flags": [],
}
CLEAN_ROW = {
    "case_id": "x",
    "artifacts": [{"content": "a"}],
    "transcript": "t",
    "ragtruth": {"id": "1"},
}


def _record(total=100, replay_of=None, council_error=False):
    return {
        "result": {
            "provenance": {
                "cost_tokens": {"total": total},
                "replay_of": replay_of,
                "council_error": council_error,
                "model_bindings": [{"role": "risk_judge", "model": "azure/x"}],
            }
        }
    }


class FakeBFF:
    """Records every request; scripted responses; raises on the ids in ``fail``."""

    def __init__(self, fail=()):
        self.calls, self.fail = [], set(fail)

    def __call__(self, method, path, body=None, tolerate=()):
        self.calls.append((method, path, body))
        assert not any("api_key" in json.dumps(b) for b in [body or {}]), (
            "a key must never ride a request"
        )
        if path == "/v1/workspaces" and method == "GET":
            return 200, {"active": body and body.get("_ws") or "ragtruth-x", "workspaces": []}
        if path == "/v1/agent/template":
            return 200, {
                "eval_profile": {
                    "council_config": {},
                    "ontology_ref": "_core/1",
                    "ontology_path": "p",
                },
                "dataset": {"case_id": "_core_fabricated_claim"},
            }
        if path.endswith("/readiness"):
            return 200, {"ok": True, "findings": []}
        if path == "/v1/cases/ingest/preview":
            return 200, {"count": len([ln for ln in body["raw"].splitlines() if ln.strip()])}
        if path == "/v1/cases":
            return 200, {"cases": [{"case_id": f"c{i}"} for i in range(self.n_cases)]}
        if path == "/v1/run-eval":
            cid = body["case_id"]
            if cid in self.fail:
                raise RuntimeError("judge exploded")
            return 200, _record()
        return 200, {}


def test_gold_leak_is_detected_and_stripped_rows_pass():
    assert cb.gold_leak([GOLD_ROW]) == [("x", "expected_safety_flags")]
    assert cb.gold_leak([CLEAN_ROW]) == []


def test_replay_and_zero_cost_records_are_not_fresh():
    assert cb.check_fresh(_record(total=0))["ok"] is False
    assert cb.check_fresh(_record(replay_of="run_123"))["ok"] is False
    assert cb.check_fresh(_record(council_error=True))["ok"] is False
    ok = cb.check_fresh(_record())
    assert ok["ok"] is True and ok["cost_total"] == 100 and ok["model_bindings"]


def test_expected_case_count_is_the_ingested_rows_only():
    # observed live 2026-09-08: GET /v1/cases lists the ingested corpus only; the pinned template
    # case is NOT unioned in (that union is /v1/cases/browser). 30 ingested -> 30 listed.
    assert cb.expected_count(30) == 30
    assert cb.expected_count(30, pinned=1) == 31


def test_ceiling_stops_before_the_next_paid_call(tmp_path):
    bff = FakeBFF()
    bff.n_cases = 6
    ids = [f"c{i}" for i in range(5)]
    report = cb.grade_cases(bff, ids, ceiling=3, out_dir=tmp_path)
    paid = [c for c in bff.calls if c[1] == "/v1/run-eval"]
    assert len(paid) == 3 and report["stopped_reason"] == "ceiling"


def test_failed_case_is_retained_as_a_failure_record(tmp_path):
    bff = FakeBFF(fail={"c1"})
    bff.n_cases = 3
    report = cb.grade_cases(bff, ["c0", "c1", "c2"], ceiling=10, out_dir=tmp_path)
    assert report["ok"] == 2 and [f["case_id"] for f in report["failed"]] == ["c1"]
    assert (tmp_path / "runs" / "c0.json").exists()


def test_workspace_is_switched_home_even_when_grading_raises(tmp_path):
    bff = FakeBFF(fail={"c0", "c1", "c2"})
    bff.n_cases = 3
    with pytest.raises(RuntimeError):
        cb.run(
            bff,
            ws="ragtruth-x",
            ingest_files=[],
            grade_ids=["c0", "c1", "c2"],
            ceiling=10,
            out_dir=tmp_path / "o",
            home_ws="home",
            abort_after_initial_failures=3,
            raise_on_abort=True,
        )
    assert bff.calls[-1] == ("POST", "/v1/workspace", {"name": "home"})


def test_corpus_superset_is_accepted_but_a_missing_ingested_id_fails(tmp_path):
    ingest = tmp_path / "in.jsonl"
    ingest.write_text(
        json.dumps({**CLEAN_ROW, "case_id": "c0"})
        + "\n"
        + json.dumps({**CLEAN_ROW, "case_id": "c1"})
        + "\n"
    )
    bff = FakeBFF()
    bff.n_cases = 5  # corpus already holds other rows: a SUPERSET must pass
    rep = cb.run(
        bff,
        ws="ragtruth-x",
        ingest_files=[ingest],
        grade_ids=["c0"],
        ceiling=1,
        out_dir=tmp_path / "a",
        home_ws="home",
    )
    assert rep["ingested"] == 2 and rep["corpus_listed"] == 5
    bff = FakeBFF()
    bff.n_cases = 1  # c1 missing from the listing -> refuse before any paid call
    with pytest.raises(RuntimeError, match="not listed"):
        cb.run(
            bff,
            ws="ragtruth-x",
            ingest_files=[ingest],
            grade_ids=["c0"],
            ceiling=1,
            out_dir=tmp_path / "b",
            home_ws="home",
        )
    assert not [c for c in bff.calls if c[1] == "/v1/run-eval"]


SNAPSHOT_LENS = {
    "policy_judge": ["FABRICATED_CLAIM", "MISSING_CONTEXT"],
    "faithfulness_judge": ["SOURCE_CONTRADICTION", "MISSING_CONTEXT", "STYLE_VIOLATION"],
}


class LensBFF(FakeBFF):
    """A judge store: GET returns the current judge dict; PUT stores it; ``wipes`` simulates a BFF
    that drops fields not present in the PUT body (the trap the memory note records)."""

    def __init__(self, stuck=False):
        super().__init__()
        self.judges = {
            r: {
                "role": r,
                "assigned_flags": [],
                "k": 3,
                "temperature": 1.0,
                "model": "",
                "provider": "",
                "criterion": "keep me",
                "display_name": "Seat",
                "validator_refs": [],
                "available_flags": SNAPSHOT_LENS[r],
            }
            for r in SNAPSHOT_LENS
        }
        self.stuck = stuck

    def __call__(self, method, path, body=None, tolerate=()):
        self.calls.append((method, path, body))
        if path.startswith("/v1/judges/"):
            role = path.split("/v1/judges/")[1].split("?")[0]
            if method == "GET":
                return 200, dict(self.judges[role])
            if method == "PUT":
                if not self.stuck:
                    self.judges[role] = {**self.judges[role], **body}
                return 200, {}
        return super().__call__(method, path, body, tolerate)


def test_lens_edit_drops_the_code_and_preserves_every_other_field():
    bff = LensBFF()
    cb.set_judge_lens(bff, "policy_judge", drop={"MISSING_CONTEXT"}, snapshot_lens=SNAPSHOT_LENS)
    put = next(b for m, p, b in bff.calls if m == "PUT" and "/v1/judges/policy_judge" in p)
    assert put["assigned_flags"] == ["FABRICATED_CLAIM"]
    for k in (
        "k",
        "temperature",
        "criterion",
        "display_name",
        "model",
        "provider",
        "validator_refs",
    ):
        assert put[k] == bff.judges["policy_judge"][k]


def test_lens_edit_refuses_to_proceed_if_the_code_is_still_there():
    bff = LensBFF(stuck=True)
    with pytest.raises(RuntimeError, match="MISSING_CONTEXT"):
        cb.set_judge_lens(
            bff, "faithfulness_judge", drop={"MISSING_CONTEXT"}, snapshot_lens=SNAPSHOT_LENS
        )


def test_run_applies_the_lens_drop_to_exactly_the_roles_that_carry_the_code(tmp_path):
    bff = LensBFF()
    bff.n_cases = 3
    cb.run(
        bff,
        ws="ragtruth-x",
        ingest_files=[],
        grade_ids=["c0"],
        ceiling=1,
        out_dir=tmp_path / "o",
        home_ws="home",
        drop_codes={"MISSING_CONTEXT"},
        snapshot_lens=SNAPSHOT_LENS,
    )
    puts = [p for m, p, b in bff.calls if m == "PUT" and "/v1/judges/" in p]
    assert sorted(p.split("/v1/judges/")[1].split("?")[0] for p in puts) == [
        "faithfulness_judge",
        "policy_judge",
    ]
    first_grade = next(i for i, c in enumerate(bff.calls) if c[1] == "/v1/run-eval")
    last_lens_get = max(
        i for i, c in enumerate(bff.calls) if c[0] == "GET" and "/v1/judges/" in c[1]
    )
    assert last_lens_get < first_grade  # lens verified BEFORE any paid call


def test_run_creates_the_workspace_on_the_requested_pack(tmp_path):
    bff = FakeBFF()
    bff.n_cases = 1
    cb.run(
        bff,
        ws="ragtruth-x",
        ingest_files=[],
        grade_ids=["c0"],
        ceiling=1,
        out_dir=tmp_path / "o",
        home_ws="home",
        pack="data_to_text",
    )
    create = next(b for m, p, b in bff.calls if m == "POST" and p == "/v1/workspaces")
    assert create["pack"] == "data_to_text"


class BindBFF(FakeBFF):
    """A workspace judge whose deployment binding can be edited (or refuses to, when stuck)."""

    def __init__(self, stuck=False):
        super().__init__()
        self.stuck = stuck
        self.judge = {
            "k": 1,
            "temperature": 0.0,
            "criterion": "c",
            "display_name": "Policy",
            "validator_refs": [],
            "assigned_flags": [],
            "provider": "",
            "model": "",
            "endpoint": "",
            "api_version": "",
        }

    def __call__(self, method, path, body=None, tolerate=()):
        if path.startswith("/v1/judges/policy_judge"):
            self.calls.append((method, path, body))
            if method == "PUT" and not self.stuck:
                self.judge.update(
                    {k: body[k] for k in ("provider", "model", "endpoint", "api_version")}
                )
            return 200, dict(self.judge)
        return super().__call__(method, path, body, tolerate)


REBIND = {
    "role": "policy_judge",
    "provider": "azure",
    "model": "gpt-4.1",
    "endpoint": "https://r.cognitiveservices.azure.com/",
    "api_version": "2024-10-21",
}


def test_rebind_sets_the_deployment_and_preserves_every_other_field():
    bff = BindBFF()
    out = cb.set_judge_binding(bff, **REBIND)
    put = next(b for m, p, b in bff.calls if m == "PUT")
    for k in ("provider", "model", "endpoint", "api_version"):
        assert put[k] == REBIND[k]
    for k in ("k", "temperature", "criterion", "display_name", "validator_refs", "assigned_flags"):
        assert put[k] == bff.judge[k]
    assert out["model"] == "gpt-4.1" and out["k"] == 1 and out["temperature"] == 0.0


def test_rebind_refuses_if_the_binding_did_not_stick():
    with pytest.raises(RuntimeError, match="did not stick"):
        cb.set_judge_binding(BindBFF(stuck=True), **REBIND)


def test_run_rebinds_before_readiness_and_before_any_paid_call(tmp_path):
    bff = BindBFF()
    bff.n_cases = 1
    rep = cb.run(
        bff,
        ws="ragtruth-x",
        ingest_files=[],
        grade_ids=["c0"],
        ceiling=1,
        out_dir=tmp_path / "o",
        home_ws="home",
        pack="data_to_text",
        rebind=[REBIND],
    )
    seq = [(m, p) for m, p, b in bff.calls]
    i_put = next(i for i, (m, p) in enumerate(seq) if m == "PUT" and "/v1/judges/policy" in p)
    i_ready = next(i for i, (m, p) in enumerate(seq) if p.endswith("/readiness"))
    i_grade = next(i for i, (m, p) in enumerate(seq) if p == "/v1/run-eval")
    assert i_put < i_ready < i_grade
    assert rep["rebind"][0]["model"] == "gpt-4.1"
