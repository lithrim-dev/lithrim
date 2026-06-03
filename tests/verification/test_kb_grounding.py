"""Offline tests for the WS-7b KB-grounding tool (compose over the live backend KB).

The first Phase-3 "Align" slice + the paper's headline mechanism: a verification
tool that disproves a confident-but-wrong council flag by GROUNDING its claim in
the knowledge base — the S-BS-7 presence-check generalized from the transcript to
the backend KB corpus.

Hermetic by construction: the ``:8002/v1/kb/{namespace}/search`` HTTP is MOCKED
via an injected fake client (the structural-floor ``grade_replay`` mirror). NO live
:8002 call is made by default. The leverage gate is asserted directly — importing
the package pulls no httpx/onnx/pinecone (httpx is lazy, behind the [verification]
extra); the bench composes over the live endpoint rather than salvaging the heavy
KB stack.

Confirmed wire contract (lithrim-backend/app/routes/kb.py:64, live 2026-06-02):

    GET :8002/v1/kb/{namespace}/search?q=<query>&top_k=<n>
    -> {"namespace","query","top_k","total_hits",
        "results":[{"id","score","text","metadata"}],"duration_ms"}
"""

from __future__ import annotations

import sys

from lithrim_bench.harness.grounding import _CONTRACT_EXECUTORS, KbGrounding, ground
from lithrim_bench.harness.ontology import from_dict
from lithrim_bench.verification import (
    REFERENCE_CONFORMANCE,
    Claim,
    KbRagTool,
    VerificationSpec,
)

# --------------------------------------------------------------------------- #
# fake :8002 KB client — mirrors KbSearchResponse; records the wire it received
# --------------------------------------------------------------------------- #
HIPAA_506_CHUNK = (
    "Uses and disclosures to carry out treatment, payment, and health care "
    "operations. A covered entity may use or disclose protected health information "
    "for treatment, payment, or health care operations as permitted by this section; "
    "consent for such disclosures is not required."
)


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p

    def raise_for_status(self):
        return None


class FakeKbHttp:
    """A fake httpx.Client-like object for GET :8002/v1/kb/{ns}/search.

    Returns ``results`` (a list of KbSearchMatch dicts) for any KB GET and records
    each call so the test can assert the exact request shape. NEVER touches a socket.
    """

    def __init__(self, *, results):
        self._results = results
        self.calls = []

    def get(self, url, params=None, headers=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        return _Resp(
            {
                "namespace": url.rstrip("/").split("/")[-2],
                "query": (params or {}).get("q"),
                "top_k": (params or {}).get("top_k"),
                "total_hits": len(self._results),
                "results": self._results,
                "duration_ms": 1,
            }
        )

    def close(self):
        pass


class _BoomKbHttp:
    """Any KB call fails — proves the floor/suppress path degrades to inconclusive
    (and that no live call is made when none should be)."""

    def get(self, *a, **k):
        raise AssertionError("KB HTTP call made when none was expected")

    def close(self):
        pass


def _match(id_, score, text, metadata=None):
    return {"id": id_, "score": score, "text": text, "metadata": metadata or {}}


def _spec(**ref):
    base = {"namespace": "hipaa", "service": "http://localhost:8002"}
    base.update(ref)
    return VerificationSpec(
        tool="kb_rag", applies_to_flags=("FABRICATED_CONSENT_SCOPE",), locus="consent", reference=base
    )


def _claim(text):
    return Claim(REFERENCE_CONFORMANCE, "FABRICATED_CONSENT_SCOPE", text, "consent", {})


# --------------------------------------------------------------------------- #
# A1 — KbRagTool.verify(): grounds / inconclusive from mocked :8002 matches
# --------------------------------------------------------------------------- #
def test_kb_tool_grounds_claim_from_mocked_match():
    http = FakeKbHttp(results=[_match("hipaa:164-506", 0.91, HIPAA_506_CHUNK)])
    res = KbRagTool(http_client=http).verify(
        _claim("disclosure for treatment payment operations consent not required"),
        _spec(min_score=0.5, match="claim_in_chunk"),
    )
    assert res.conforms is True  # KB grounds the claim -> the flag MAY be cleared
    assert res.evidence["corroborated_ids"] == ["hipaa:164-506"]
    assert res.evidence["top_score"] == 0.91
    assert res.manifest["tool"] == "kb_rag" and res.manifest["namespace"] == "hipaa"


def test_kb_tool_uses_confirmed_wire_contract():
    # REGRESSION GUARD on the confirmed :8002 contract: GET /v1/kb/{ns}/search?q=&top_k=
    http = FakeKbHttp(results=[_match("x", 0.9, HIPAA_506_CHUNK)])
    KbRagTool(http_client=http).verify(
        _claim("disclosure for treatment payment operations"),
        _spec(top_k=7, match="claim_in_chunk"),
    )
    assert len(http.calls) == 1
    call = http.calls[0]
    assert call["url"] == "http://localhost:8002/v1/kb/hipaa/search"
    assert call["params"]["q"] == "disclosure for treatment payment operations"
    assert call["params"]["top_k"] == 7
    # no api key configured in this hermetic env -> header omitted (open/dev backend)
    assert call["headers"] == {}


def test_kb_tool_inconclusive_when_no_match():
    http = FakeKbHttp(results=[])  # empty corpus hit
    res = KbRagTool(http_client=http).verify(_claim("anything"), _spec(min_score=0.5))
    assert res.conforms is None  # KB silence is NOT proof -> never clears the flag
    assert res.evidence["retrieved"] == 0


def test_kb_tool_inconclusive_below_min_score():
    http = FakeKbHttp(results=[_match("x", 0.2, HIPAA_506_CHUNK)])
    res = KbRagTool(http_client=http).verify(
        _claim("disclosure for treatment payment operations"),
        _spec(min_score=0.5, match="claim_in_chunk"),
    )
    assert res.conforms is None  # a hit exists but does not clear the pinned threshold
    assert res.evidence["scored"] == 0


def test_kb_tool_inconclusive_when_predicate_unmet():
    # a high-score hit whose text does NOT corroborate the claim tokens -> inconclusive,
    # not a silent clear (presence alone is not grounding when a predicate is pinned).
    http = FakeKbHttp(results=[_match("x", 0.99, "totally unrelated billing modifier rules")])
    res = KbRagTool(http_client=http).verify(
        _claim("zidovudine antiretroviral dosing schedule"),
        _spec(min_score=0.5, match="claim_in_chunk"),
    )
    assert res.conforms is None
    assert res.evidence["corroborated_ids"] == []


def test_kb_tool_endpoint_error_is_inconclusive_not_clear():
    res = KbRagTool(http_client=_BoomKbHttp()).verify(_claim("x"), _spec(min_score=0.5))
    assert res.conforms is None  # transport/HTTP error -> inconclusive, never a fabricated hit
    assert "error" in res.manifest


def test_kb_tool_expect_absent_disproves_on_hit():
    # the disprove-by-retrieval direction: the SME pins expect="absent" (a claim of
    # absence). A clearing KB hit DISPROVES it -> VIOLATION (conforms False).
    http = FakeKbHttp(results=[_match("hipaa:164-506", 0.9, HIPAA_506_CHUNK)])
    res = KbRagTool(http_client=http).verify(
        _claim("disclosure for treatment payment operations"),
        _spec(min_score=0.5, match="claim_in_chunk", expect="absent"),
    )
    assert res.conforms is False


def test_kb_tool_no_live_call_by_default():
    # injected fake client => zero sockets; and httpx stays unimported by the tool path.
    http = FakeKbHttp(results=[_match("x", 0.9, HIPAA_506_CHUNK)])
    KbRagTool(http_client=http).verify(_claim("disclosure treatment payment"), _spec())
    assert len(http.calls) == 1  # exactly the one mocked GET, no retries / extra calls


# --------------------------------------------------------------------------- #
# A2 — kb_grounding contract executor in ground(): S-BS-7 generalized (suppress)
# --------------------------------------------------------------------------- #
def test_kb_grounding_is_registered_in_suppress_registry():
    assert _CONTRACT_EXECUTORS.get("kb_grounding") is KbGrounding


def _kb_ontology():
    """A minimal ontology declaring ONE kb_grounding suppress contract on a confident
    flag. FABRICATED_CONSENT_SCOPE blocks (weight 1.0 >= block_at_or_above)."""
    return from_dict(
        {
            "ontology_version": "kb_grounding_test_v1",
            "domain": "test",
            "flags": [
                {
                    "flag": "FABRICATED_CONSENT_SCOPE",
                    "category": "policy",
                    "definition": "",
                    "when_to_use": "",
                    "when_NOT_to_use": "",
                    "owner_roles": ["policy_judge"],
                    "tier": "tier1",
                    "gradeable": True,
                }
            ],
            "questions": [],
            "verification_contracts": [
                {
                    "flag_code": "FABRICATED_CONSENT_SCOPE",
                    "question": "Does the KB ground the disclosure the council flagged?",
                    "contract_type": "kb_grounding",
                    "version": "v1",
                    "params": {
                        "namespace": "hipaa",
                        "service": "http://localhost:8002",
                        "claim_field": "detail",
                        "min_score": 0.5,
                        "match": "claim_in_chunk",
                    },
                }
            ],
            "severity_map": {
                "weights": {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.1},
                "block_at_or_above": 1.0,
                "warn_above": 0.0,
            },
        }
    )


# a confident BLOCK-driving council finding the KB will disprove (the FP we suppress)
_COUNCIL_BLOCK = {
    "verdict": "BLOCK",
    "findings": [
        {
            "code": "FABRICATED_CONSENT_SCOPE",
            "severity": "HIGH",
            "detail": "disclosure for treatment payment operations consent not required",
        }
    ],
}
_CASE = {"artifacts": [{"type": "scribe_note", "content": "consent for TPO disclosure"}]}


def test_kb_grounding_suppresses_confident_wrong_flag_and_flips_verdict():
    """A2 — the S-BS-7 generalization: a confident flag the KB disproves is suppressed,
    flipping the re-scored verdict BLOCK -> PASS. Offline, injected fake http_client."""
    http = FakeKbHttp(results=[_match("hipaa:164-506", 0.92, HIPAA_506_CHUNK)])
    g = ground(_COUNCIL_BLOCK, _CASE, ontology=_kb_ontology(), http_client=http)

    assert g.original_verdict == "BLOCK"
    assert g.verdict == "PASS"  # the only blocking finding was suppressed by KB grounding
    assert [f.get("code") for f in g.active] == []
    assert len(g.suppressed) == 1
    sup = g.suppressed[0]
    assert sup["finding"]["code"] == "FABRICATED_CONSENT_SCOPE"
    assert sup["verdict"].disproved is True
    assert sup["verdict"].matched_token == "hipaa:164-506"
    # it composed over the confirmed :8002 wire
    assert http.calls[0]["url"] == "http://localhost:8002/v1/kb/hipaa/search"


def test_kb_grounding_keeps_flag_when_kb_does_not_ground_it():
    """Conservative inverse: a KB miss leaves the flag ACTIVE (never clears by silence)
    -> the verdict stays BLOCK."""
    http = FakeKbHttp(results=[])  # KB returns nothing relevant
    g = ground(_COUNCIL_BLOCK, _CASE, ontology=_kb_ontology(), http_client=http)
    assert g.verdict == "BLOCK"
    assert [f.get("code") for f in g.active] == ["FABRICATED_CONSENT_SCOPE"]
    assert g.suppressed == []


def test_kb_grounding_endpoint_error_keeps_flag_active():
    """A KB transport error is inconclusive -> the flag stays active (BLOCK holds)."""
    g = ground(_COUNCIL_BLOCK, _CASE, ontology=_kb_ontology(), http_client=_BoomKbHttp())
    assert g.verdict == "BLOCK"
    assert [f.get("code") for f in g.active] == ["FABRICATED_CONSENT_SCOPE"]


# --------------------------------------------------------------------------- #
# A5 — leverage gate: no heavy KB stack pulled at import
# --------------------------------------------------------------------------- #
def test_no_heavy_kb_deps_imported_by_the_tool_path():
    # importing + constructing the tool/contract must not pull httpx/onnx/pinecone.
    KbRagTool()
    assert not ({"onnxruntime", "pinecone", "pymongo"} & set(sys.modules)), (
        "leverage gate: the bench composes over :8002, it must NOT salvage the heavy KB stack"
    )
