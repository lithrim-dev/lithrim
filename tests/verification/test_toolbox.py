"""Offline test suite for the WS-3 verification toolbox core (promoted to main).

No network, no Synthea CSV, no live :3031 (the StructuralJute HTTP client is
mocked; RecordRag is exercised via the in-memory FakeRecordRagTool). Fixtures
mirror the confirmed real `scribe_v1` shapes.

Scope note: the spike's `grounding.py` back-compat shim and the `KbRagTool` tests
do NOT live here — the shim is spike throwaway (main has `harness/grounding.py`),
and the KB/RAG stack is deferred to WS-3b. The structural-floor wiring of the
toolbox into the harness is covered by `tests/verification/test_grounding_floor.py`.
"""

from __future__ import annotations

import json

from lithrim_bench.verification import (
    CLEARED,
    UNRESOLVED,
    Claim,
    FakeRecordRagTool,
    InRowTool,
    JuteGenValidatorTool,
    RecordRagTool,
    Router,
    StructuralJuteTool,
    VerificationSpec,
    compose_verdict,
)
from lithrim_bench.verification.spec import RECORD_PRESENCE, STRUCTURAL_CONFORMANCE

# --------------------------------------------------------------------------- #
# fixtures (mirror confirmed scribe_v1 shapes)
# --------------------------------------------------------------------------- #
CLEAN_ROW = {
    "patient_profile": {
        "conditions": ["Hyperlipidemia (disorder)", "Ischemic heart disease (disorder)"],
        "active_medications": ["Clopidogrel 75 MG Oral Tablet", "Simvastatin 20 MG Oral Tablet"],
    }
}
CLEAN_SOAP = (
    "SUBJECTIVE: stable.\n"
    "PMH:\n"
    "  - Hyperlipidemia (disorder)\n"
    "  - Ischemic heart disease (disorder)\n"
    "ASSESSMENT: stable.\n"
    "PLAN:\n"
    "1. Continue Simvastatin 20 MG daily\n"
)
INJECT_SOAP = (
    "SUBJECTIVE: stable.\n"
    "PMH:\n"
    "  - Hyperlipidemia (disorder)\n"
    "  - Ischemic heart disease (disorder)\n"
    "  - Diabetes mellitus type 2 (disorder)\n"
    "ASSESSMENT: stable.\n"
)
DOSAGE_ROW = {
    "patient_profile": {
        "conditions": ["Gingivitis (disorder)"],
        "active_medications": ["Acetaminophen 300 MG / Hydrocodone Bitartrate 5 MG Oral Tablet"],
    }
}
DOSAGE_DRIFT_SOAP = (
    "ASSESSMENT: Gingivitis (disorder).\n"
    "PLAN:\n"
    "1. Continue Acetaminophen 3000MG / Hydrocodone Bitartrate 5 MG Oral Tablet 300 MG daily\n"
    "2. Follow-up in 1 month\n"
)
DOSAGE_CLEAN_SOAP = (
    "ASSESSMENT: Gingivitis (disorder).\n"
    "PLAN:\n"
    "1. Continue Acetaminophen 300 MG / Hydrocodone Bitartrate 5 MG Oral Tablet daily\n"
)

PMH_SPEC = VerificationSpec(
    tool="in_row",
    applies_to_flags=("FABRICATED_HISTORY",),
    locus="PMH",
    reference={
        "oracle_path": "patient_profile.conditions",
        "extractor": "soap_pmh_items",
        "match": "snomed_core",
    },
)
DOSE_SPEC = VerificationSpec(
    tool="in_row",
    applies_to_flags=("WRONG_DOSAGE",),
    locus="dosage",
    reference={
        "oracle_path": "patient_profile.active_medications",
        "extractor": "soap_plan_dose_tokens",
        "match": "dose_token",
    },
)


def _claim(soap, row, flag, locus):
    return Claim(RECORD_PRESENCE, flag, soap, locus, row)


def _raises(exc_type, fn):
    try:
        fn()
    except exc_type:
        return True
    except Exception as other:  # noqa: BLE001
        raise AssertionError(
            f"expected {exc_type.__name__}, got {type(other).__name__}: {other}"
        ) from None
    raise AssertionError(f"expected {exc_type.__name__}, nothing raised")


# --------------------------------------------------------------------------- #
# InRowTool — record presence (the proven primitive)
# --------------------------------------------------------------------------- #
def test_in_row_pmh_clean_conforms():
    res = InRowTool().verify(_claim(CLEAN_SOAP, CLEAN_ROW, "FABRICATED_HISTORY", "PMH"), PMH_SPEC)
    assert res.conforms is True
    assert res.evidence["ungrounded"] == []
    assert res.manifest["deterministic"] is True


def test_in_row_pmh_inject_violation():
    res = InRowTool().verify(_claim(INJECT_SOAP, CLEAN_ROW, "FABRICATED_HISTORY", "PMH"), PMH_SPEC)
    assert res.conforms is False
    assert res.evidence["ungrounded"] == ["Diabetes mellitus type 2 (disorder)"]


def test_in_row_dose_clean_conforms():
    res = InRowTool().verify(
        _claim(DOSAGE_CLEAN_SOAP, DOSAGE_ROW, "WRONG_DOSAGE", "dosage"), DOSE_SPEC
    )
    assert res.conforms is True
    assert res.evidence["ungrounded"] == []


def test_in_row_dose_drift_violation():
    res = InRowTool().verify(
        _claim(DOSAGE_DRIFT_SOAP, DOSAGE_ROW, "WRONG_DOSAGE", "dosage"), DOSE_SPEC
    )
    assert res.conforms is False
    # the mutated dose is ungrounded; the genuine doses (5 MG / 300 MG) are grounded
    assert [d.replace(" ", "").upper() for d in res.evidence["ungrounded"]] == ["3000MG"]


def test_in_row_wrong_oracle_does_not_catch_dose():
    # routing the dosage drift to the PMH/conditions oracle (the v3 mistake) MISSES it
    res = InRowTool().verify(_claim(DOSAGE_DRIFT_SOAP, DOSAGE_ROW, "WRONG_DOSAGE", "PMH"), PMH_SPEC)
    assert res.conforms is True  # no PMH items -> nothing ungrounded -> would WRONGLY clear


# --------------------------------------------------------------------------- #
# spec validation
# --------------------------------------------------------------------------- #
def test_spec_rejects_unknown_tool():
    _raises(
        ValueError,
        lambda: VerificationSpec(tool="bogus", applies_to_flags=("X",), locus="", reference={}),
    )


def test_spec_rejects_missing_reference_keys():
    _raises(
        ValueError,
        lambda: VerificationSpec(
            tool="in_row", applies_to_flags=("X",), locus="", reference={"oracle_path": "p"}
        ),
    )


def test_spec_rejects_bad_selector():
    _raises(
        ValueError,
        lambda: VerificationSpec(
            tool="structural_jute",
            applies_to_flags=("X",),
            locus="",
            reference={
                "service": "http://x",
                "mapping_selector": {"value": 1},
                "artifact_kind": "hl7",
            },
        ),
    )


def test_spec_normalizes_flags_to_tuple():
    s = VerificationSpec(
        tool="in_row",
        applies_to_flags=["A", "B"],
        locus="",
        reference={"oracle_path": "p", "extractor": "soap_pmh_items", "match": "snomed_core"},
    )
    assert s.applies_to_flags == ("A", "B")


# --------------------------------------------------------------------------- #
# Router + compose_verdict — the false-negative guardrail
# --------------------------------------------------------------------------- #
def _router():
    return Router([PMH_SPEC, DOSE_SPEC], [InRowTool()])


def _builder(soap, row):
    def build(flag, spec):
        return _claim(soap, row, flag, spec.locus)

    return build


def test_router_maps_flag_to_spec():
    r = _router()
    assert r.spec_for("FABRICATED_HISTORY") is PMH_SPEC
    assert r.spec_for("WRONG_DOSAGE") is DOSE_SPEC
    assert r.spec_for("HALLUCINATED_DETAIL") is None
    assert r.routed_flags == {"FABRICATED_HISTORY", "WRONG_DOSAGE"}


def test_compose_clear_all_approves():
    out = compose_verdict(
        open_flags=["FABRICATED_HISTORY"],
        router=_router(),
        claim_builder=_builder(CLEAN_SOAP, CLEAN_ROW),
    )
    assert out["verdict"] == "approve"
    assert out["cleared"] == ["FABRICATED_HISTORY"]
    assert out["decisions"][0]["disposition"] == CLEARED
    assert out["decisions"][0]["manifest"]["tool"] == "in_row"  # manifest logged per verdict


def test_compose_confirmed_rejects():
    out = compose_verdict(
        open_flags=["FABRICATED_HISTORY"],
        router=_router(),
        claim_builder=_builder(INJECT_SOAP, CLEAN_ROW),
    )
    assert out["verdict"] == "reject"
    assert out["confirmed"] == ["FABRICATED_HISTORY"]


def test_compose_unrouted_flag_stays_open():
    # THE guardrail: a flag with no matched tool is UNRESOLVED, never silently cleared
    out = compose_verdict(
        open_flags=["HALLUCINATED_DETAIL"],
        router=_router(),
        claim_builder=_builder(CLEAN_SOAP, CLEAN_ROW),
    )
    assert out["verdict"] == "reject"
    assert out["unresolved"] == ["HALLUCINATED_DETAIL"]
    assert out["decisions"][0]["disposition"] == UNRESOLVED


def test_compose_mixed_clear_and_confirm_rejects():
    out = compose_verdict(
        open_flags=["FABRICATED_HISTORY", "WRONG_DOSAGE"],
        router=_router(),
        claim_builder=_builder(
            DOSAGE_DRIFT_SOAP, DOSAGE_ROW
        ),  # no PMH (FH clears) + drifted dose (WD confirms)
    )
    assert out["verdict"] == "reject"
    assert out["cleared"] == ["FABRICATED_HISTORY"]
    assert out["confirmed"] == ["WRONG_DOSAGE"]


def test_compose_tool_error_is_unresolved_not_cleared():
    class BoomTool(InRowTool):
        def verify(self, claim, spec):
            raise RuntimeError("boom")

    r = Router([PMH_SPEC], [BoomTool()])
    out = compose_verdict(
        open_flags=["FABRICATED_HISTORY"], router=r, claim_builder=_builder(CLEAN_SOAP, CLEAN_ROW)
    )
    assert out["verdict"] == "reject"
    assert out["unresolved"] == ["FABRICATED_HISTORY"]


def test_compose_no_flags_approves():
    out = compose_verdict(
        open_flags=[], router=_router(), claim_builder=_builder(CLEAN_SOAP, CLEAN_ROW)
    )
    assert out["verdict"] == "approve"


# --------------------------------------------------------------------------- #
# StructuralJuteTool — mocked :3031 (correct contract + content-hash pin)
# --------------------------------------------------------------------------- #
class _Resp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p

    def raise_for_status(self):
        return None


class FakeHttp:
    def __init__(self, mappings, parse_resp, apply_resp):
        self.mappings, self.parse_resp, self.apply_resp = mappings, parse_resp, apply_resp
        self.calls = []

    def get(self, url):
        self.calls.append(("GET", url, None))
        if url.endswith("/mappings"):
            return _Resp(self.mappings)
        raise AssertionError(f"unexpected GET {url}")

    def post(self, url, json=None):
        self.calls.append(("POST", url, json))
        if url.endswith("/parse-hl7"):
            return _Resp(self.parse_resp)
        if "/apply" in url:
            return _Resp(self.apply_resp)
        raise AssertionError(f"unexpected POST {url}")

    def close(self):
        pass


_MAPPINGS = [
    {"id": 25, "title": "hl7-dft-p03-validator", "content": {"yaml": "dft"}},
    {"id": 26, "title": "hl7-adt-a04-validator", "content": {"yaml": "adt-a04-checks"}},
]
_PARSE_OK = {"valid": True, "parsed": {"MSH": {}, "PID": {"birth_date": {"time": "19800101"}}}}
_APPLY_PASS = {
    "result": {
        "checks": [
            {"name": "msh-present", "status": "pass"},
            {"name": "pid-present", "status": "pass"},
        ]
    },
    "org/id": "x",
}
_APPLY_FAIL = {
    "result": {
        "checks": [
            {
                "name": "dob-format-valid",
                "field": "PID.birth_date",
                "status": "fail",
                "message": "bad dob",
            }
        ]
    },
    "org/id": "x",
}

_JUTE_SPEC = VerificationSpec(
    tool="structural_jute",
    applies_to_flags=("STRUCTURAL_NONCONFORMANCE",),
    locus="artifact",
    reference={
        "service": "http://localhost:3031",
        "mapping_selector": {"by": "title", "value": "hl7-adt-a04-validator"},
        "artifact_kind": "hl7_adt_a04",
    },
)


def test_structural_conforms_and_uses_correct_wire_contract():
    http = FakeHttp(_MAPPINGS, _PARSE_OK, _APPLY_PASS)
    res = StructuralJuteTool(http_client=http).verify(
        _claim("MSH|...", {}, None, "artifact"), _JUTE_SPEC
    )
    assert res.conforms is True
    assert res.manifest["resolved_id"] == 26 and res.manifest["drift"] is False
    # REGRESSION GUARD vs the stale etlp_structural.py: correct body keys + correct mapping id
    assert ("POST", "http://localhost:3031/parse-hl7", {"message": "MSH|..."}) in http.calls
    assert (
        "POST",
        "http://localhost:3031/mappings/26/apply",
        {"data": {"resource": {"MSH": {}, "PID": {"birth_date": {"time": "19800101"}}}}},
    ) in http.calls


def test_structural_violation():
    res = StructuralJuteTool(http_client=FakeHttp(_MAPPINGS, _PARSE_OK, _APPLY_FAIL)).verify(
        _claim("MSH|...", {}, None, "artifact"), _JUTE_SPEC
    )
    assert res.conforms is False
    assert res.evidence["failed"] and res.evidence["failed"][0]["name"] == "dob-format-valid"


def test_structural_drift_refuses():
    spec = VerificationSpec(
        tool="structural_jute",
        applies_to_flags=("X",),
        locus="artifact",
        reference={**_JUTE_SPEC.reference, "pinned_content_sha256": "0" * 64},  # wrong pin
    )
    res = StructuralJuteTool(http_client=FakeHttp(_MAPPINGS, _PARSE_OK, _APPLY_PASS)).verify(
        _claim("MSH|...", {}, None, "artifact"), spec
    )
    assert res.conforms is None  # drift -> refuse, neither clears nor confirms
    assert res.manifest["drift"] is True


def test_structural_pin_matches_observed_hash():
    tool = StructuralJuteTool(http_client=FakeHttp(_MAPPINGS, _PARSE_OK, _APPLY_PASS))
    observed = StructuralJuteTool._content_hash(_MAPPINGS[1])  # the id=26 mapping
    spec = VerificationSpec(
        tool="structural_jute",
        applies_to_flags=("X",),
        locus="artifact",
        reference={**_JUTE_SPEC.reference, "pinned_content_sha256": observed},
    )
    res = tool.verify(_claim("MSH|...", {}, None, "artifact"), spec)
    assert res.conforms is True and res.manifest["drift"] is False


def test_structural_mapping_not_found():
    spec = VerificationSpec(
        tool="structural_jute",
        applies_to_flags=("X",),
        locus="artifact",
        reference={
            "service": "http://localhost:3031",
            "mapping_selector": {"by": "title", "value": "does-not-exist"},
            "artifact_kind": "hl7_adt_a04",
        },
    )
    res = StructuralJuteTool(http_client=FakeHttp(_MAPPINGS, _PARSE_OK, _APPLY_PASS)).verify(
        _claim("MSH|...", {}, None, "artifact"), spec
    )
    assert res.conforms is None and res.manifest["drift"] == "mapping_not_found"


# --------------------------------------------------------------------------- #
# RecordRag — offline fake (interface + manifest determinism) + not-configured guard
# --------------------------------------------------------------------------- #
_RAG_SPEC = VerificationSpec(
    tool="record_rag",
    applies_to_flags=("UNSUPPORTED_CLAIM",),
    locus="artifact",
    reference={
        "client": "lithrim_search_sdk",
        "filters": {"corpus_version": "2023", "document_ids": ["policy-7"]},
        "min_score": 0.5,
    },
)
_CORPUS = {
    "policy-7": "minimum necessary phi disclosure standard for clinical documentation",
    "policy-9": "billing code modifier rules",
}


def test_fake_rag_conforms_on_pinned_hit():
    claim = Claim(
        RECORD_PRESENCE, "UNSUPPORTED_CLAIM", "minimum necessary phi disclosure", "artifact", {}
    )
    res = FakeRecordRagTool(_CORPUS).verify(claim, _RAG_SPEC)
    assert res.conforms is True
    assert res.manifest["retrieval_order"][0] == "policy-7"
    assert "context_hash" in res.manifest


def test_fake_rag_inconclusive_when_no_hit():
    claim = Claim(
        RECORD_PRESENCE, "UNSUPPORTED_CLAIM", "zzz totally unrelated tokens", "artifact", {}
    )
    res = FakeRecordRagTool(_CORPUS).verify(claim, _RAG_SPEC)
    assert res.conforms is None  # no retrieval -> inconclusive, NOT a clear


def test_fake_rag_manifest_is_deterministic():
    claim = Claim(
        RECORD_PRESENCE, "UNSUPPORTED_CLAIM", "minimum necessary phi disclosure", "artifact", {}
    )
    a = FakeRecordRagTool(_CORPUS).verify(claim, _RAG_SPEC).manifest
    b = FakeRecordRagTool(_CORPUS).verify(claim, _RAG_SPEC).manifest
    assert a == b  # same input -> identical manifest (stable order + context hash)


def test_record_rag_not_configured_raises():
    # the real SDK is not installed in the spike venv -> a clear RuntimeError, not a silent pass
    claim = Claim(RECORD_PRESENCE, "UNSUPPORTED_CLAIM", "x", "artifact", {})
    _raises(RuntimeError, lambda: RecordRagTool().verify(claim, _RAG_SPEC))


# --------------------------------------------------------------------------- #
# JuteGenValidatorTool — generate-from-sample validator (mocked Copilot + test-template)
# --------------------------------------------------------------------------- #
import hashlib as _hashlib  # noqa: E402

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
_FAIL_OUT = {
    "request": {
        "checks": [
            {"name": "has-identifier", "field": "identifier", "status": "pass", "message": "ok"},
            {
                "name": "valid-birthdate",
                "field": "birthDate",
                "status": "fail",
                "message": "not a date",
            },
        ]
    }
}


class FakeGenHttp:
    def __init__(self, *, gen_template="$body: x", tt_output=None, compiled=True, mappings=None):
        self.gen_template, self.tt_output, self.compiled = gen_template, tt_output, compiled
        self.mappings = mappings or [
            {"id": 23, "title": "fhir-patient-validator", "content": {"yaml": "$body: base"}}
        ]
        self.calls = []

    def get(self, url):
        self.calls.append(("GET", url, None))
        if url.endswith("/mappings"):
            return _Resp(self.mappings)
        raise AssertionError(url)

    def post(self, url, json=None):
        self.calls.append(("POST", url, json))
        if url.endswith("/mappings/generate"):
            return _Resp(
                {"template": self.gen_template, "confidence": "partial", "retries_used": 1}
            )
        if url.endswith("/mappings/test-template"):
            return _Resp(
                {
                    "compiled": self.compiled,
                    "output": self.tt_output,
                    "error": None if self.compiled else "boom",
                }
            )
        raise AssertionError(url)

    def close(self):
        pass


def _gen_spec(**ref):
    base = {"service": "http://localhost:3031", "artifact_kind": "fhir_patient"}
    base.update(ref)
    return VerificationSpec(
        tool="jute_gen", applies_to_flags=("X",), locus="artifact", reference=base
    )


def test_jute_gen_pinned_template_conforms():
    http = FakeGenHttp(tt_output=_PASS_OUT)
    tmpl = "$body: pinned-validator"
    spec = _gen_spec(
        pinned_template=tmpl, pinned_template_sha256=_hashlib.sha256(tmpl.encode()).hexdigest()
    )
    res = JuteGenValidatorTool(http_client=http).verify(
        Claim(STRUCTURAL_CONFORMANCE, None, _PATIENT, "artifact", {}), spec
    )
    assert res.conforms is True
    assert res.manifest["template_source"] == "pinned" and res.manifest["deterministic"] is True


def test_jute_gen_pinned_drift_refuses():
    http = FakeGenHttp(tt_output=_PASS_OUT)
    spec = _gen_spec(pinned_template="$body: pinned", pinned_template_sha256="0" * 64)
    res = JuteGenValidatorTool(http_client=http).verify(
        Claim(STRUCTURAL_CONFORMANCE, None, _PATIENT, "artifact", {}), spec
    )
    assert res.conforms is None


def test_jute_gen_generates_then_applies_and_caches():
    http = FakeGenHttp(gen_template="$body: generated", tt_output=_FAIL_OUT)
    tool = JuteGenValidatorTool(http_client=http)
    spec = _gen_spec(
        generate={
            "description": "fix birthDate",
            "base_validator": "fhir-patient-validator",
            "sample_input": {
                "identifier": [{"value": "x"}],
                "name": [{"family": "Doe", "given": ["J"]}],
                "gender": "male",
            },
        }
    )
    r1 = tool.verify(Claim(STRUCTURAL_CONFORMANCE, None, _PATIENT, "artifact", {}), spec)
    assert r1.conforms is False  # _FAIL_OUT has a failing check
    assert r1.manifest["template_source"] == "generated" and r1.manifest["confidence"] == "partial"
    assert r1.evidence["failed"][0]["name"] == "valid-birthdate"
    # generate-once: a second verify reuses the cached template (no 2nd /mappings/generate)
    tool.verify(Claim(STRUCTURAL_CONFORMANCE, None, _PATIENT, "artifact", {}), spec)
    gen_calls = [c for c in http.calls if c[0] == "POST" and c[1].endswith("/mappings/generate")]
    assert len(gen_calls) == 1


def test_jute_gen_uncompiled_is_inconclusive():
    http = FakeGenHttp(gen_template="$body: bad", tt_output=None, compiled=False)
    spec = _gen_spec(
        generate={
            "description": "x",
            "base_validator": "fhir-patient-validator",
            "sample_input": {"gender": "male"},
            "expected_output": {"checks": []},
        }
    )
    res = JuteGenValidatorTool(http_client=http).verify(
        Claim(STRUCTURAL_CONFORMANCE, None, _PATIENT, "artifact", {}), spec
    )
    assert res.conforms is None  # template didn't compile -> never silently clears
