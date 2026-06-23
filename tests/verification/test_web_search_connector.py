"""Offline tests for the CONN-WEBSEARCH-1 web_search reference connector.

The one net-new reference connector for the community release (Cycle 3, spec §4).
The CORE design decision is a SAFETY POSTURE: ``web_search`` is NON-AUTHORITATIVE
BY CONSTRUCTION. Web results are unverifiable, so the executor MUST NEVER clear or
raise a finding — it ALWAYS resolves ``conforms=None`` (inconclusive) and merely
ATTACHES retrieved snippets/citations + a structured ``web_support`` assessment to
the finding's evidence (for the SME / withstands-gate to weigh). Present (citations
attached) or absent (unavailable), it can never flip a verdict.

Hermetic by construction: the search service HTTP is MOCKED via an injected fake
client (the ``KbRagTool`` / structural-floor ``grade_replay`` mirror). NO live call
is made. The leverage gate is asserted directly — importing the package pulls no
httpx/heavy stacks (httpx is lazy, behind the [verification] extra).

The covered acceptance criteria (driver A–H):
  A — declaration + provenance (kind:tool, tier:core, transport:service; present under deny)
  B — spec wiring + missing-``query`` raise
  C — mocked-present -> conforms=None with citations/snippets/web_support
  D — absent (no key/endpoint) -> conforms=None, no network
  E — transport error -> conforms=None with the error in evidence
  F — ground() leaves the finding ACTIVE (un-suppressed)
  G — NON-VACUOUS: a high-score SUPPORTING mock STILL yields conforms=None + active finding
  H — leverage gate: no heavy deps pulled at import
"""

from __future__ import annotations

import sys

import pytest

from lithrim_bench.harness import plugins as P
from lithrim_bench.harness.grounding import _CONTRACT_EXECUTORS, WebSearchGrounding, ground
from lithrim_bench.harness.ontology import from_dict
from lithrim_bench.verification import Claim, VerificationSpec, WebSearchTool

# --------------------------------------------------------------------------- #
# fake search service client — records the wire it received, NEVER touches a socket
# --------------------------------------------------------------------------- #
SUPPORTING_SNIPPET = (
    "The reference document confirms the disputed assertion verbatim, with a stable "
    "citation URL and a matching title."
)


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p

    def raise_for_status(self):
        return None


class FakeWebHttp:
    """A fake httpx.Client-like object for the web-search service. Returns ``results``
    (citation dicts) for any GET/POST and records each call. NEVER touches a socket."""

    def __init__(self, *, results, web_support="supports"):
        self._results = results
        self._web_support = web_support
        self.calls = []

    def get(self, url, params=None, headers=None):
        self.calls.append({"verb": "GET", "url": url, "params": params, "headers": headers})
        return _Resp(
            {
                "query": (params or {}).get("q"),
                "results": self._results,
                "web_support": self._web_support,
            }
        )

    def post(self, url, json=None, headers=None):
        self.calls.append({"verb": "POST", "url": url, "json": json, "headers": headers})
        return _Resp(
            {
                "query": (json or {}).get("query") or (json or {}).get("q"),
                "results": self._results,
                "web_support": self._web_support,
            }
        )

    def close(self):
        pass


class _BoomWebHttp:
    """Any call fails — proves the connector degrades to inconclusive, never raises out."""

    def get(self, *a, **k):
        raise RuntimeError("web search service unreachable")

    def post(self, *a, **k):
        raise RuntimeError("web search service unreachable")

    def close(self):
        pass


def _citation(url, title, snippet, score=0.9):
    return {"url": url, "title": title, "snippet": snippet, "score": score}


def _spec(**ref):
    base = {"query": "the disputed assertion", "service": "http://localhost:8585"}
    base.update(ref)
    return VerificationSpec(
        tool="web_search", applies_to_flags=("SOME_FLAG",), locus="claim", reference=base
    )


def _claim(text):
    return Claim("reference_conformance", "SOME_FLAG", text, "claim", {})


# --------------------------------------------------------------------------- #
# A — declaration + provenance
# --------------------------------------------------------------------------- #
def test_web_search_is_a_declared_core_tool_plugin():
    tools = {p.id: (p.kind, p.tier, p.transport, p.implements) for p in P.tool_plugins()}
    assert tools.get("web_search") == ("tool", "core", "service", "tool.mcp_server")


def test_web_search_appears_in_provenance_snapshot():
    snap = P.provenance_snapshot()
    assert "web_search" in {p["id"] for p in snap["plugins"]}


def test_web_search_is_core_so_present_under_a_denying_license():
    # core ⇒ never gated: a deny-all license still records it (only tier:pro is gated).
    snap = P.provenance_snapshot(P.License("deny-all"))
    assert "web_search" in {p["id"] for p in snap["plugins"]}


# --------------------------------------------------------------------------- #
# B — spec wiring + missing-key raise
# --------------------------------------------------------------------------- #
def test_web_search_spec_constructs_with_query():
    spec = _spec()
    assert spec.tool == "web_search" and spec.reference["query"] == "the disputed assertion"


def test_web_search_spec_missing_query_raises():
    with pytest.raises(ValueError) as exc:
        VerificationSpec(
            tool="web_search", applies_to_flags=("SOME_FLAG",), locus="claim", reference={}
        )
    assert "query" in str(exc.value)


# --------------------------------------------------------------------------- #
# C — execution (mocked, present) -> conforms=None with citations/snippets/web_support
# --------------------------------------------------------------------------- #
def test_web_search_present_attaches_citations_but_stays_inconclusive():
    http = FakeWebHttp(
        results=[_citation("https://ref/1", "Reference", SUPPORTING_SNIPPET, 0.91)],
        web_support="supports",
    )
    res = WebSearchTool(http_client=http).verify(_claim("the disputed assertion"), _spec())
    # NON-AUTHORITATIVE BY CONSTRUCTION: a present, supporting result is STILL inconclusive.
    assert res.conforms is None
    assert res.evidence["query"] == "the disputed assertion"
    assert res.evidence["citations"] == ["https://ref/1"]
    assert SUPPORTING_SNIPPET in res.evidence["snippets"]
    assert res.evidence["web_support"] == "supports"
    assert res.manifest["tool"] == "web_search"


# --------------------------------------------------------------------------- #
# D — graceful-absent (no key/endpoint) -> conforms=None, NO network
# --------------------------------------------------------------------------- #
def test_web_search_absent_endpoint_is_inconclusive_no_network(monkeypatch):
    for var in (
        "LITHRIM_WEB_SEARCH_BASE_URL",
        "LITHRIM_WEB_SEARCH_API_KEY",
        "LITHRIM_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    # no service in the reference + no env -> unavailable, no network attempted.
    spec = VerificationSpec(
        tool="web_search",
        applies_to_flags=("SOME_FLAG",),
        locus="claim",
        reference={"query": "anything"},
    )
    res = WebSearchTool(http_client=_BoomWebHttp()).verify(_claim("anything"), spec)
    assert res.conforms is None
    assert res.evidence.get("web_search") == "unavailable"
    assert res.evidence.get("query") == "anything"


# --------------------------------------------------------------------------- #
# E — transport error (mock raises) -> conforms=None with the error in evidence
# --------------------------------------------------------------------------- #
def test_web_search_transport_error_is_inconclusive_not_a_clear():
    res = WebSearchTool(http_client=_BoomWebHttp()).verify(_claim("x"), _spec())
    assert res.conforms is None  # transport error -> inconclusive, never raises out
    assert "error" in res.evidence


# --------------------------------------------------------------------------- #
# F — ground() integration: the finding stays ACTIVE whether the service supports / errors
# --------------------------------------------------------------------------- #
def test_web_search_is_registered_in_suppress_registry():
    assert _CONTRACT_EXECUTORS.get("web_search") is WebSearchGrounding


def _web_ontology():
    """A minimal ontology declaring ONE web_search contract on a confident flag.
    SOME_FLAG blocks (weight 1.0 >= block_at_or_above)."""
    return from_dict(
        {
            "ontology_version": "web_search_test_v1",
            "domain": "test",
            "flags": [
                {
                    "flag": "SOME_FLAG",
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
                    "flag_code": "SOME_FLAG",
                    "question": "Does a web search support the disputed assertion?",
                    "contract_type": "web_search",
                    "version": "v1",
                    "params": {
                        "query": "the disputed assertion",
                        "service": "http://localhost:8585",
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


_COUNCIL_BLOCK = {
    "verdict": "BLOCK",
    "findings": [
        {
            "code": "SOME_FLAG",
            "severity": "HIGH",
            "detail": "the disputed assertion is fabricated",
        }
    ],
}
_CASE = {"artifacts": [{"type": "note", "content": "a note that contains the disputed assertion"}]}


def test_web_search_ground_keeps_finding_active_when_supporting():
    http = FakeWebHttp(
        results=[_citation("https://ref/1", "Reference", SUPPORTING_SNIPPET, 0.9)],
        web_support="supports",
    )
    g = ground(_COUNCIL_BLOCK, _CASE, ontology=_web_ontology(), http_client=http)
    # the finding is NEVER suppressed by web evidence -> verdict holds.
    assert g.original_verdict == "BLOCK"
    assert g.verdict == "BLOCK"
    assert [f.get("code") for f in g.active] == ["SOME_FLAG"]
    assert g.suppressed == []


def test_web_search_ground_keeps_finding_active_when_contradicting():
    http = FakeWebHttp(
        results=[_citation("https://ref/2", "Reference", "the assertion is contradicted", 0.8)],
        web_support="contradicts",
    )
    g = ground(_COUNCIL_BLOCK, _CASE, ontology=_web_ontology(), http_client=http)
    assert g.verdict == "BLOCK"
    assert [f.get("code") for f in g.active] == ["SOME_FLAG"]
    assert g.suppressed == []


def test_web_search_ground_keeps_finding_active_on_transport_error():
    g = ground(_COUNCIL_BLOCK, _CASE, ontology=_web_ontology(), http_client=_BoomWebHttp())
    assert g.verdict == "BLOCK"
    assert [f.get("code") for f in g.active] == ["SOME_FLAG"]
    assert g.suppressed == []


# --------------------------------------------------------------------------- #
# G — NON-VACUOUS guarantee: even a high-score SUPPORTING mock leaves it inconclusive + active
# --------------------------------------------------------------------------- #
def test_web_search_non_vacuous_high_score_support_never_clears():
    # a maximal supporting response (top score, explicit "supports") MUST NOT clear the flag —
    # the structural non-authoritative guarantee is real, not a vacuous "no service so None".
    http = FakeWebHttp(
        results=[_citation("https://ref/strong", "Strong match", SUPPORTING_SNIPPET, 0.999)],
        web_support="supports",
    )
    res = WebSearchTool(http_client=http).verify(_claim("the disputed assertion"), _spec())
    assert res.conforms is None  # never True
    assert res.evidence["web_support"] == "supports"  # the support WAS observed and attached
    assert res.evidence["citations"] == ["https://ref/strong"]

    g = ground(_COUNCIL_BLOCK, _CASE, ontology=_web_ontology(), http_client=http)
    assert g.verdict == "BLOCK"  # high-score support did NOT flip the verdict
    assert g.suppressed == []
    assert [f.get("code") for f in g.active] == ["SOME_FLAG"]


# --------------------------------------------------------------------------- #
# H — leverage gate: no heavy deps pulled at import / construction
# --------------------------------------------------------------------------- #
def test_no_heavy_deps_imported_by_the_web_search_path():
    WebSearchTool()
    assert not ({"onnxruntime", "pinecone", "pymongo"} & set(sys.modules)), (
        "leverage gate: the connector composes over a service, it must NOT pull a heavy stack"
    )
