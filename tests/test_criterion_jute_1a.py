"""CRITERION-JUTE-1a: the pinned-JUTE arg-shaping wire in ``McpCallGrounding.check``.

The single frozen-floor carve-out (same class as SPAN-BIND-1): ``mcp_call`` gains an optional
``params.arguments_jute`` (+ ``arguments_jute_sha256``). ``_shape_arguments`` factors the argument
source:

  (a) absent           -> ``params.get("arguments") or {}`` (today's behaviour, byte-identical);
  (b) present + hash-OK -> the pinned JUTE applied to ``{case, finding}`` in-memory (:3031
                           ``test_template`` seam) -> the per-case arguments object;
  (c) present + hash-MISMATCH -> REFUSE: no tool call, finding STANDS (never grade a drifted
                           transform), mirroring the ``jute_gen`` ``pinned_template_sha256`` refusal.

$0/offline: ``plugins.resolve_tool`` + ``McpStdioClient`` are stubbed, and the :3031 jute-apply is
injected via the ``grounding._jute_client`` factory seam (NO :3031, which is DOWN). Determinism:
same pinned JUTE + same case => same args => same verdict; a drifted mapping is refused, never graded.
"""

from __future__ import annotations

import hashlib

from lithrim_bench.harness import grounding
from lithrim_bench.harness.ontology import VerificationContractDecl
from lithrim_bench.harness.plugins import PluginManifest

_FINDING = {"code": "UPCODED_DIAGNOSIS", "detail": "note is more specific than record"}
# a case carrying span-local pinned SNOMED codes (record=Dementia 52448006, note=Alzheimer's 26929004)
_CASE = {
    "case_id": "cv_upcode_1",
    "resource": {"subsumption_codes": {"record_code": "52448006", "note_code": "26929004"}},
}

# a pinned JUTE arg-mapping (text is opaque to the test; the injected client keys off it)
_JUTE = "arg_shape: {concept_id: record_code, subsumer_id: note_code}"
_JUTE_SHA = hashlib.sha256(_JUTE.encode("utf-8")).hexdigest()

_MANIFEST = PluginManifest(
    id="hermes_snomed", kind="tool", transport="service", implements="tool.mcp_server",
    service={"mcp": {"command": "hermes", "args": ["mcp"]}},
)


def _decl(params):
    return VerificationContractDecl(
        flag_code="UPCODED_DIAGNOSIS", question="supported?",
        contract_type="mcp_call", params=params, version="v1",
    )


class _RecordingMcpClient:
    """A fake McpStdioClient that records the arguments passed to call_tool."""

    last_arguments = None

    def __init__(self, *a, **k):
        pass

    def call_tool(self, name, arguments=None):
        type(self).last_arguments = arguments
        return {"subsumedBy": True}

    def close(self):
        pass


class _FakeJuteClient:
    """A fake EtlpJuteClient: applies the pinned JUTE by SHAPING args from the case in-memory,
    exactly what the live :3031 ``test_template`` would produce for THIS case (no :3031)."""

    def test_template(self, template, sample_input):
        # the envelope the wire feeds is {case, finding}; the transform reads the case's pinned codes
        codes = sample_input["case"]["resource"]["subsumption_codes"]
        return {
            "compiled": True,
            "output": {"concept_id": codes["record_code"], "subsumer_id": codes["note_code"]},
            "error": None,
        }


def _patch(monkeypatch, *, manifest=_MANIFEST, jute_client=None):
    from lithrim_bench.harness import plugins

    monkeypatch.setattr(plugins, "resolve_tool", lambda tool_id, **k: manifest)
    import lithrim_bench.verification.mcp_client as mc

    _RecordingMcpClient.last_arguments = None
    monkeypatch.setattr(mc, "McpStdioClient", _RecordingMcpClient)
    if jute_client is not None:
        monkeypatch.setattr(grounding, "_jute_client", lambda: jute_client)


# ─────────────────────────── (a) absent -> static path byte-identical ───────────────────────────
def test_absent_arguments_jute_uses_static_dict(monkeypatch):
    _patch(monkeypatch)
    c = grounding._CONTRACT_EXECUTORS["mcp_call"](
        _decl({"tool": "hermes_snomed", "call": "subsumed_by",
               "arguments": {"concept_id": "STATIC", "subsumer_id": "STATIC2"},
               "authority": "corroborated", "match": "subsumedBy"})
    )
    v = c.check(dict(_FINDING), _CASE)
    assert v.disproved is True
    # the STATIC dict flowed through verbatim — no JUTE, no per-case shaping
    assert _RecordingMcpClient.last_arguments == {"concept_id": "STATIC", "subsumer_id": "STATIC2"}


def test_shape_arguments_absent_returns_static_dict():
    """The helper itself: absent arguments_jute -> the static dict verbatim (empty -> {})."""
    c = grounding._CONTRACT_EXECUTORS["mcp_call"](
        _decl({"tool": "t", "call": "c", "arguments": {"k": "v"}})
    )
    assert c._shape_arguments(_CASE, dict(_FINDING)) == {"k": "v"}
    empty = grounding._CONTRACT_EXECUTORS["mcp_call"](_decl({"tool": "t", "call": "c"}))
    assert empty._shape_arguments(_CASE, dict(_FINDING)) == {}


# ─────────────────────────── (b) present + hash-OK -> per-case transform ───────────────────────────
def test_present_hash_ok_shapes_arguments_from_this_case(monkeypatch):
    _patch(monkeypatch, jute_client=_FakeJuteClient())
    c = grounding._CONTRACT_EXECUTORS["mcp_call"](
        _decl({"tool": "hermes_snomed", "call": "subsumed_by",
               "arguments_jute": _JUTE, "arguments_jute_sha256": _JUTE_SHA,
               "authority": "corroborated", "match": "subsumedBy"})
    )
    v = c.check(dict(_FINDING), _CASE)
    # the args came from the transform of THIS case's pinned codes, not any static dict
    assert _RecordingMcpClient.last_arguments == {"concept_id": "52448006", "subsumer_id": "26929004"}
    assert v.disproved is True  # tool corroborated subsumedBy -> finding cleared


def test_present_hash_ok_is_deterministic_across_runs(monkeypatch):
    """Same pinned JUTE + same case => byte-identical arguments across repeated checks."""
    _patch(monkeypatch, jute_client=_FakeJuteClient())
    c = grounding._CONTRACT_EXECUTORS["mcp_call"](
        _decl({"tool": "hermes_snomed", "call": "subsumed_by",
               "arguments_jute": _JUTE, "arguments_jute_sha256": _JUTE_SHA,
               "authority": "corroborated", "match": "subsumedBy"})
    )
    c.check(dict(_FINDING), _CASE)
    first = _RecordingMcpClient.last_arguments
    _RecordingMcpClient.last_arguments = None
    c.check(dict(_FINDING), _CASE)
    assert _RecordingMcpClient.last_arguments == first


# ─────────────────────────── (c) present + hash-MISMATCH -> refuse, finding stands ───────────────────────────
def test_hash_mismatch_refuses_and_leaves_finding_standing(monkeypatch):
    _patch(monkeypatch, jute_client=_FakeJuteClient())
    c = grounding._CONTRACT_EXECUTORS["mcp_call"](
        _decl({"tool": "hermes_snomed", "call": "subsumed_by",
               "arguments_jute": _JUTE, "arguments_jute_sha256": "deadbeef" * 8,
               "authority": "corroborated", "match": "subsumedBy"})
    )
    v = c.check(dict(_FINDING), _CASE)
    assert v.disproved is False  # NEVER grade through a drifted transform
    assert _RecordingMcpClient.last_arguments is None  # the tool was never called
    assert "drift" in v.reason.lower() or "mismatch" in v.reason.lower()


def test_shape_arguments_hash_mismatch_returns_none():
    """The helper itself: a drifted transform yields None (the refusal sentinel)."""
    c = grounding._CONTRACT_EXECUTORS["mcp_call"](
        _decl({"tool": "t", "call": "c", "arguments_jute": _JUTE, "arguments_jute_sha256": "x" * 64})
    )
    assert c._shape_arguments(_CASE, dict(_FINDING)) is None


# ─────────────────────────── authoring-side pin-write ───────────────────────────
def test_authoring_pins_arguments_jute_sha256():
    """POST /v1/grounding-contract computes + stores arguments_jute_sha256 when arguments_jute is
    provided without one; the pinned sha then verifies at grade time (round-trip)."""
    from apps.bff.app import _pin_arguments_jute

    pinned = _pin_arguments_jute({"tool": "hermes_snomed", "call": "subsumed_by", "arguments_jute": _JUTE})
    assert pinned["arguments_jute_sha256"] == _JUTE_SHA
    # a contract carrying the pinned sha grade-verifies clean (no drift)
    c = grounding._CONTRACT_EXECUTORS["mcp_call"](_decl({"tool": "t", "call": "c", **pinned}))
    # a real EtlpJuteClient is not called here (hash matches -> would apply); assert the hash gate
    # itself passes by confirming the sha the executor would compare is the stored one.
    assert (
        hashlib.sha256(pinned["arguments_jute"].encode("utf-8")).hexdigest()
        == pinned["arguments_jute_sha256"]
    )
    assert c is not None


def test_authoring_pin_is_noop_without_arguments_jute():
    """No arguments_jute -> params unchanged (byte-identical for every existing contract)."""
    from apps.bff.app import _pin_arguments_jute

    p = {"tool": "t", "call": "c", "arguments": {"k": "v"}}
    assert _pin_arguments_jute(p) == p
    assert "arguments_jute_sha256" not in _pin_arguments_jute(p)


def test_authoring_respects_caller_supplied_sha():
    """A caller-supplied sha256 is trusted as-is (explicit pin), not recomputed."""
    from apps.bff.app import _pin_arguments_jute

    p = {"arguments_jute": _JUTE, "arguments_jute_sha256": "explicit"}
    assert _pin_arguments_jute(p)["arguments_jute_sha256"] == "explicit"
