"""Offline tests for the DSPy JUTE validator generator + the bench_accept metric.

No network, no LLM: `:3031` is replaced by a Python oracle (FakeJuteClient) and the DSPy
LM is replaced by an injected fake predictor. The real by-construction pack is the fixture
(it is the acceptance oracle the metric exists to apply).
"""

from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from lithrim_bench.verification import (
    GOLDEN_US_CORE_PATIENT_VALIDATOR,
    Claim,
    EtlpJuteClient,
    JuteGenValidatorTool,
    VerificationSpec,
    best_of_n,
    build_generator,
    feedback_from,
    make_bench_metric,
    score_template,
    strip_fences,
)
from lithrim_bench.verification.spec import STRUCTURAL_CONFORMANCE

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK = REPO_ROOT / "data" / "verification_packs" / "fhir_patient_v1.jsonl"


@pytest.fixture
def cases() -> list[dict]:
    return [json.loads(line) for line in PACK.read_text().splitlines() if line.strip()]


# --------------------------------------------------------------------------- #
# FakeJuteClient — a Python oracle standing in for the live :3031 engine. The
# validator's intent is encoded by a tag in the template string, so score_template
# can be exercised deterministically without JUTE.
# --------------------------------------------------------------------------- #
def _bd_valid(bd) -> bool:
    if bd is None:
        return True  # optional: absent is valid
    return len(bd) > 0 and bd[0].isdigit() and all(c.isdigit() or c == "-" for c in bd)


def _checks_for(patient: dict, *, birthdate: str) -> list[dict]:
    name = patient.get("name")
    has_name = (
        isinstance(name, list)
        and len(name) > 0
        and bool(name[0].get("family"))
        and bool(name[0].get("given"))
    )
    if birthdate == "required":  # the seeded bug: birthDate REQUIRED
        bd_ok = bool(patient.get("birthDate")) and _bd_valid(patient.get("birthDate"))
    elif birthdate == "nodatatype":  # present always passes -> misses malformed
        bd_ok = True
    else:  # "optional" -> the golden behavior
        bd_ok = _bd_valid(patient.get("birthDate"))

    def chk(name_, ok):
        return {"name": name_, "field": name_, "status": "pass" if ok else "fail", "message": ""}

    return [
        chk("has-identifier", bool(patient.get("identifier"))),
        chk("has-name", has_name),
        chk("valid-gender", patient.get("gender") in ("male", "female", "other", "unknown")),
        chk("valid-birthdate", bd_ok),
        chk("has-telecom", bool(patient.get("telecom"))),
    ]


class FakeJuteClient:
    _TAGS = ("noncompile", "required", "nodatatype", "golden")

    def __init__(self, default: str = "golden") -> None:
        self.default = default
        self.persisted: list[tuple[str, str]] = []

    def _kind(self, template: str) -> str:
        for tag in self._TAGS:
            if tag in (template or ""):
                return tag
        return self.default

    def test_template(self, template: str, patient: dict) -> dict:
        kind = self._kind(template)
        if kind == "noncompile":
            return {"compiled": False, "output": None, "error": "Jute compile: boom"}
        checks = _checks_for(
            patient, birthdate=kind if kind in ("required", "nodatatype") else "optional"
        )
        return {"compiled": True, "output": {"request": {"checks": checks}}, "error": None}

    @staticmethod
    def find_checks(output):
        from lithrim_bench.verification.tools import StructuralJuteTool

        return StructuralJuteTool._find_checks(output)

    def persist_or_update(self, title: str, yaml_template: str) -> dict:
        self.persisted.append((title, yaml_template))
        return {"id": 777, "title": title, "action": "created"}


# --------------------------------------------------------------------------- #
# the metric (the whole point): accept iff 0 FP, 0 ERR, all defects caught
# --------------------------------------------------------------------------- #
def test_metric_accepts_golden_behavior(cases):
    s = score_template(FakeJuteClient("golden"), "golden", cases)
    assert s["accepted"] is True
    assert s["caught"] == s["defects"] == 6
    assert s["fp"] == 0 and s["err"] == 0 and s["graded"] == 1.0


def test_metric_rejects_birthdate_required_on_optional_control(cases):
    # the seeded Copilot bug: birthDate REQUIRED -> false-positives the optional-field control
    s = score_template(FakeJuteClient("required"), "required", cases)
    assert s["accepted"] is False and s["fp"] >= 1
    fps = [r for r in s["rows"] if r["exp"] == "PASS" and r["verdict"] == "BLOCK"]
    assert any(r["defect"] == "strip_optional_field" for r in fps)


def test_metric_rejects_no_datatype_check_misses_malformed(cases):
    # birthDate present-always-passes -> misses the wrong_datatype defect
    s = score_template(FakeJuteClient("nodatatype"), "nodatatype", cases)
    assert s["accepted"] is False and s["caught"] < s["defects"]
    misses = [r for r in s["rows"] if r["exp"] == "BLOCK" and r["verdict"] != "BLOCK"]
    assert any(r["defect"] == "wrong_datatype" for r in misses)


def test_metric_rejects_noncompiling(cases):
    s = score_template(FakeJuteClient("noncompile"), "noncompile", cases)
    assert s["accepted"] is False and s["err"] == len(cases)


def test_bench_metric_graded_and_bootstrap_gate(cases):
    good = make_bench_metric(FakeJuteClient("golden"), cases)
    gp = types.SimpleNamespace(jute_template="golden")
    assert good(None, gp) == 1.0  # graded path
    assert good(None, gp, trace=[]) is True  # bootstrap gate: accepted-only demos

    bad = make_bench_metric(FakeJuteClient("required"), cases)
    bp = types.SimpleNamespace(jute_template="required")
    assert bad(None, bp) < 1.0
    assert bad(None, bp, trace=[]) is False
    assert good(None, types.SimpleNamespace(jute_template=""), trace=[]) is False


def test_feedback_names_fp_miss_and_compile(cases):
    assert "FALSE POSITIVE" in feedback_from(
        score_template(FakeJuteClient("required"), "required", cases)
    )
    assert "MISSED" in feedback_from(
        score_template(FakeJuteClient("nodatatype"), "nodatatype", cases)
    )
    assert (
        "COMPILE"
        in feedback_from(score_template(FakeJuteClient("noncompile"), "noncompile", cases)).upper()
    )


def test_strip_fences():
    assert strip_fences("```yaml\n$body: x\n```") == "$body: x"
    assert strip_fences("```\n$body: y\n```") == "$body: y"
    assert strip_fences("$body: z") == "$body: z"


# --------------------------------------------------------------------------- #
# EtlpJuteClient — wire client (the id-from-Location parse is the key regression)
# --------------------------------------------------------------------------- #
class _Resp:
    def __init__(self, payload=None, *, headers=None):
        self._p = payload
        self.headers = headers or {}

    def json(self):
        return self._p

    def raise_for_status(self):
        return None


class FakeClientHttp:
    def __init__(
        self, *, location="http://localhost:3031/mappings/100", mappings=None, tt=None, dsl=None
    ):
        self.location, self.mappings, self.tt, self.dsl = location, mappings or [], tt, dsl
        self.put_calls, self.delete_calls, self.post_calls = [], [], []

    def get(self, url):
        if url.endswith("/jute-dsl-spec.json"):
            return _Resp(self.dsl or {"jute_dsl_spec": {"version": "1"}})
        if url.endswith("/mappings"):
            return _Resp(self.mappings)
        raise AssertionError(url)

    def post(self, url, json=None):
        self.post_calls.append((url, json))
        if url.endswith("/mappings/test-template"):
            return _Resp(
                self.tt or {"compiled": True, "output": {"request": {"checks": []}}, "error": None}
            )
        if url.endswith("/mappings"):
            return _Resp(None, headers={"Location": self.location})
        raise AssertionError(url)

    def put(self, url, json=None):
        self.put_calls.append((url, json))
        return _Resp(None)

    def delete(self, url):
        self.delete_calls.append(url)
        return _Resp(None)

    def close(self):
        pass


def test_client_create_parses_id_from_location_last_segment():
    # regression: the id is the LAST path segment, NOT the first integer (the :3031 port)
    c = EtlpJuteClient(http_client=FakeClientHttp(location="http://localhost:3031/mappings/100"))
    assert c.create_mapping("t", "$body: x")["id"] == 100


def test_client_create_id_unaffected_by_port_in_host():
    c = EtlpJuteClient(http_client=FakeClientHttp(location="http://example.com:3031/mappings/42"))
    assert c.create_mapping("t", "y")["id"] == 42


def test_client_test_template_and_find_checks():
    tt = {
        "compiled": True,
        "output": {"request": {"checks": [{"name": "x", "status": "pass"}]}},
        "error": None,
    }
    c = EtlpJuteClient(http_client=FakeClientHttp(tt=tt))
    r = c.test_template("$body: x", {"a": 1})
    assert r["compiled"] and c.find_checks(r["output"])[0]["name"] == "x"


def test_client_get_dsl_spec_unwraps():
    c = EtlpJuteClient(http_client=FakeClientHttp(dsl={"jute_dsl_spec": {"version": "9"}}))
    assert c.get_dsl_spec() == {"version": "9"}


def test_client_persist_or_update_creates_then_updates():
    http = FakeClientHttp(mappings=[])
    created = EtlpJuteClient(http_client=http).persist_or_update("foo", "$body: a")
    assert created["action"] == "created" and created["id"] == 100

    http2 = FakeClientHttp(mappings=[{"id": 50, "title": "foo", "content": {"yaml": "a"}}])
    updated = EtlpJuteClient(http_client=http2).persist_or_update("foo", "$body: new")
    assert updated["action"] == "updated" and updated["id"] == 50 and http2.put_calls


# --------------------------------------------------------------------------- #
# the DSPy refine loop (fake predictor — exercises feedback + convergence, no LM)
# --------------------------------------------------------------------------- #
class FakePredictor:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict] = []

    def __call__(self, **kw):
        self.calls.append(kw)
        out = self.outputs.pop(0) if self.outputs else "golden"
        return types.SimpleNamespace(jute_template=out)


def test_refine_loop_feeds_error_back_and_converges(cases):
    pytest.importorskip("dspy")  # build_generator builds a dspy.Module; skip without the extra
    # iter0 returns a non-compiling template; iter1 returns a golden one -> converges
    pred = FakePredictor(["a noncompile template", "a golden template"])
    gen = build_generator(FakeJuteClient(), "DSL", cases, max_iters=3, predictor=pred)
    out = gen.forward(conformance_rules="rules", sample_input={"gender": "male"})

    assert out.accepted is True
    assert len(out.history) == 2
    assert out.history[0]["err"] > 0 and out.history[1]["accepted"] is True
    # the 2nd generation received non-empty feedback naming the compile failure
    assert pred.calls[0]["prior_error"] == ""
    assert "COMPILE" in pred.calls[1]["prior_error"].upper()


def test_refine_loop_stops_at_max_iters_when_never_accepted(cases):
    pytest.importorskip("dspy")
    pred = FakePredictor(["required tmpl", "required tmpl", "required tmpl", "required tmpl"])
    gen = build_generator(FakeJuteClient(), "DSL", cases, max_iters=2, predictor=pred)
    out = gen.forward(conformance_rules="r", sample_input={"gender": "male"})
    assert out.accepted is False and len(out.history) == 2  # bounded


def test_best_of_n_returns_first_accepted(cases):
    pytest.importorskip("dspy")
    # first factory call yields a non-accepting run, second yields an accepting one
    seq = [["required tmpl"], ["golden tmpl"]]

    def make_gen():
        return build_generator(
            FakeJuteClient(), "DSL", cases, max_iters=1, predictor=FakePredictor(seq.pop(0))
        )

    out = best_of_n(make_gen, "rules", {"gender": "male"}, n=2)
    assert out.accepted is True


# --------------------------------------------------------------------------- #
# wired tool: engine="dspy" authoring + persist-via-id (the "expose to our tool" path)
# --------------------------------------------------------------------------- #
_PATIENT = json.dumps(
    {"identifier": [{"value": "x"}], "name": [{"family": "Doe", "given": ["J"]}], "gender": "male"}
)
_PASS_OUT = {
    "request": {
        "checks": [
            {"name": "has-identifier", "field": "identifier", "status": "pass", "message": "ok"}
        ]
    }
}


class FakeApplyHttp:
    """Minimal httpx stand-in for JuteGenValidatorTool's in-memory apply (test-template)."""

    def __init__(self, tt_output):
        self.tt_output = tt_output
        self.calls = []

    def post(self, url, json=None):
        self.calls.append((url, json))
        if url.endswith("/mappings/test-template"):
            return _Resp({"compiled": True, "output": self.tt_output, "error": None})
        raise AssertionError(url)

    def close(self):
        pass


def _gen_spec(**ref):
    base = {"service": "http://localhost:3031", "artifact_kind": "fhir_patient"}
    base.update(ref)
    return VerificationSpec(
        tool="jute_gen", applies_to_flags=("X",), locus="artifact", reference=base
    )


def test_jute_gen_dspy_engine_authors_and_persists():
    persist = FakeJuteClient()
    tool = JuteGenValidatorTool(
        http_client=FakeApplyHttp(_PASS_OUT),
        template_provider=lambda: GOLDEN_US_CORE_PATIENT_VALIDATOR,
        persist_client=persist,
    )
    spec = _gen_spec(
        generate={"engine": "dspy"},
        persist=True,
        persist_title="fhir-us-core-patient-validator-dspy",
    )
    res = tool.verify(Claim(STRUCTURAL_CONFORMANCE, None, _PATIENT, "artifact", {}), spec)

    assert res.conforms is True
    assert res.manifest["template_source"] == "generated" and res.manifest["engine"] == "dspy"
    assert (
        res.manifest["persisted_mapping_id"] == 777 and res.manifest["persist_action"] == "created"
    )
    assert persist.persisted and persist.persisted[0][0] == "fhir-us-core-patient-validator-dspy"


def test_jute_gen_dspy_engine_requires_provider():
    tool = JuteGenValidatorTool(http_client=FakeApplyHttp(_PASS_OUT))  # no provider
    spec = _gen_spec(generate={"engine": "dspy"})
    with pytest.raises(RuntimeError):
        tool.verify(Claim(STRUCTURAL_CONFORMANCE, None, _PATIENT, "artifact", {}), spec)
