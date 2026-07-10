"""FLOOR-BATTERY-1: the `snomed_battery` grounding SUPPRESS executor.

An ORDERED terminology battery (checks 1-3 + 7) over a note-vs-record diagnosis, run through a
SNOMED MCP tool (Hermes) exactly the way `McpCallGrounding` resolves + opens its client. It CLEARS
a raised finding (disproved=True) ONLY on positive terminology evidence:

  1. VALIDITY  — both the note and record codes exist (`concept` RAISES McpError on a bad id);
  2. MISLABEL  — the note_term matches SOME description (synonym) of note_code, not just the FSN;
  3. CATEGORY  — the note and record FSN semantic tags ((disorder)/(finding)/...) match;
  7. IS-A      — the record is-a the note (the SUPPORTED generalization) => SUPPRESS.

The three asymmetries hold: never clear an UPCODE (note strict-descendant of record), never clear
without a positive subsumedBy / valid+labeled result, and DEFER (finding stands) on any
error/silence/absence. SUPPRESS -> disproved=True; STAND and DEFER -> disproved=False.

$0/offline: `plugins.resolve_tool` is stubbed to a stdio-MCP manifest, `McpStdioClient` is a fake
that dispatches on tool name (and raises `McpError` for `concept` on a "bad" id), and the :3031
jute-apply is injected via the `grounding._jute_client` factory seam. NETWORKLESS.

Real cases as fixtures: record=Alzheimer's 26929004 / note=Dementia 52448006 (clears — Alzheimer's
is-a Dementia); the mislabel case note_code 239928004 FSN "Microscopic polyarteritis nodosa" vs
note_term "Granulomatosis with polyangiitis" (stands via check2).
"""

from __future__ import annotations

import hashlib

from lithrim_bench.harness import grounding
from lithrim_bench.harness.ontology import VerificationContractDecl
from lithrim_bench.harness.plugins import PluginManifest
from lithrim_bench.verification.mcp_client import McpError

_FINDING = {"code": "UPCODED_DIAGNOSIS", "detail": "note is more specific than record"}
_CASE = {"case_id": "cv_snomed_1"}

# a pinned JUTE arg-mapping (opaque text; the injected jute client keys off the case, not the text)
_JUTE = "battery_shape: {record_code, record_term, note_code, note_term}"
_JUTE_SHA = hashlib.sha256(_JUTE.encode("utf-8")).hexdigest()

_MANIFEST = PluginManifest(
    id="hermes_snomed", kind="tool", transport="service", implements="tool.mcp_server",
    service={"mcp": {"command": "hermes", "args": ["mcp"]}},
)


def _decl(params):
    return VerificationContractDecl(
        flag_code="UPCODED_DIAGNOSIS", question="supported?",
        contract_type="snomed_battery", params=params, version="v1",
    )


class _FakeHermes:
    """A fake McpStdioClient standing in for Hermes SNOMED. Dispatches on the tool name against a
    tiny in-memory concept table; `concept` RAISES McpError for an id not in the table (check 1's
    validity branch). `subsumes` maps (child, parent) -> subsumedBy so check 7 has a direction."""

    def __init__(self, *, concepts, subsumes, missing=(), descriptions=None, error_on=None):
        # concepts: {code -> fsn}, subsumes: {(child, parent) -> bool}, missing: codes that don't exist
        self._concepts = concepts
        self._subsumes = subsumes
        self._missing = set(missing)
        self._descriptions = descriptions or {}
        self._error_on = error_on  # a tool name that raises McpError mid-battery
        self.closed = False

    def call_tool(self, name, arguments=None):
        arguments = arguments or {}
        if self._error_on and name == self._error_on:
            raise McpError(f"{name} unreachable")
        if name == "concept":
            cid = int(arguments["concept_id"])
            if cid in self._missing:
                raise McpError(f"concept {cid} does not exist")
            return {"id": cid}
        if name == "fully_specified_name":
            cid = int(arguments["concept_id"])
            return {"term": self._concepts[cid]}
        if name == "descriptions":
            cid = int(arguments["concept_id"])
            return [{"term": t} for t in self._descriptions.get(cid, [])]
        if name == "subsumed_by":
            child = int(arguments["concept_id"])
            parent = int(arguments["subsumer_id"])
            return {"subsumedBy": bool(self._subsumes.get((child, parent)))}
        raise McpError(f"unknown tool {name!r}")

    def close(self):
        self.closed = True


class _FakeJuteClient:
    """A fake EtlpJuteClient: applies the pinned battery JUTE by shaping the 4 fields the executor
    needs (record_code/record_term/note_code/note_term) from the case in-memory (no :3031)."""

    def __init__(self, shaped):
        self._shaped = shaped

    def test_template(self, template, sample_input):
        return {"compiled": True, "output": dict(self._shaped), "error": None}


class _NullShapeJuteClient:
    """A jute client whose transform yields no object (absent/None shape) -> the finding stands."""

    def test_template(self, template, sample_input):
        return {"compiled": True, "output": None, "error": None}


def _patch(monkeypatch, *, manifest=_MANIFEST, client=None, jute_client=None):
    from lithrim_bench.harness import plugins

    monkeypatch.setattr(plugins, "resolve_tool", lambda tool_id, **k: manifest)
    import lithrim_bench.verification.mcp_client as mc

    if client is not None:
        monkeypatch.setattr(mc, "McpStdioClient", lambda *a, **k: client)
    if jute_client is not None:
        monkeypatch.setattr(grounding, "_jute_client", lambda: jute_client)


def _executor(params):
    return grounding._CONTRACT_EXECUTORS["snomed_battery"](_decl(params))


# The Alzheimer's/Dementia clearing fixture. Alzheimer's 26929004 is-a Dementia 52448006.
_ALZ = 26929004
_DEM = 52448006

# The SUPPORTED-clear case: note=Dementia (the general term), record=Alzheimer's (record is-a note).
_CLEAR_CONCEPTS = {_ALZ: "Alzheimer's disease (disorder)", _DEM: "Dementia (disorder)"}
_CLEAR_SUBSUMES = {(_ALZ, _DEM): True, (_DEM, _ALZ): False}
_CLEAR_DESCR = {_DEM: ["Dementia", "Dementia (disorder)"]}


def _clear_params():
    return {
        "tool": "hermes_snomed",
        "arguments_jute": _JUTE, "arguments_jute_sha256": _JUTE_SHA,
    }


def _clear_shape():
    # record=Alzheimer's (specific), note=Dementia (general) -> record is-a note (supported)
    return {"record_code": str(_ALZ), "record_term": "Alzheimer's disease",
            "note_code": str(_DEM), "note_term": "Dementia"}


# ─────────────────────────── registration ───────────────────────────
def test_registered_as_a_core_suppress_executor():
    assert "snomed_battery" in grounding._CONTRACT_EXECUTORS
    assert grounding._CONTRACT_EXECUTORS["snomed_battery"].contract_type == "snomed_battery"


# ─────────────────────────── 1. clears on the supported generalization ───────────────────────────
def test_clears_on_valid_labeled_same_category_record_isa_note(monkeypatch):
    fake = _FakeHermes(concepts=_CLEAR_CONCEPTS, subsumes=_CLEAR_SUBSUMES, descriptions=_CLEAR_DESCR)
    _patch(monkeypatch, client=fake, jute_client=_FakeJuteClient(_clear_shape()))
    v = _executor(_clear_params()).check(dict(_FINDING), _CASE)
    assert v.disproved is True  # CLEAR: record is-a note (supported)
    assert "check7" in v.reason and ("record is-a note" in v.reason or "supported" in v.reason)


# ─────────────────────────── 2. check 1 VALIDITY: a bad code stands ───────────────────────────
def test_invalid_note_code_stands_check1(monkeypatch):
    fake = _FakeHermes(concepts={_DEM: "Dementia (disorder)"}, subsumes={}, missing={_ALZ})
    _patch(monkeypatch, client=fake, jute_client=_FakeJuteClient({
        "record_code": str(_DEM), "record_term": "Dementia",
        "note_code": str(_ALZ), "note_term": "Alzheimer's",
    }))
    v = _executor(_clear_params()).check(dict(_FINDING), _CASE)
    assert v.disproved is False  # NEVER clear: the note code does not exist
    assert "check1" in v.reason and "note" in v.reason


# ─────────────────────────── 3. check 2 MISLABEL ───────────────────────────
def test_mislabel_note_term_matches_no_description_stands_check2(monkeypatch):
    # note_code 239928004 FSN "Microscopic polyarteritis nodosa"; note_term is a DIFFERENT disease
    NOTE = 239928004
    fake = _FakeHermes(
        concepts={NOTE: "Microscopic polyarteritis nodosa (disorder)", _DEM: "Dementia (disorder)"},
        subsumes={},
        descriptions={NOTE: ["Microscopic polyarteritis nodosa", "Microscopic polyangiitis"]},
    )
    _patch(monkeypatch, client=fake, jute_client=_FakeJuteClient({
        "record_code": str(_DEM), "record_term": "Dementia",
        "note_code": str(NOTE), "note_term": "Granulomatosis with polyangiitis",
    }))
    v = _executor(_clear_params()).check(dict(_FINDING), _CASE)
    assert v.disproved is False  # note_term matches no synonym of note_code -> stands
    assert "check2" in v.reason and "mislabel" in v.reason.lower()


def test_synonym_note_term_passes_check2(monkeypatch):
    # note_term matches a NON-FSN description (a synonym); check 2 must PASS (not flag) and,
    # with same category + record is-a note, the finding CLEARS.
    NOTE = 239928004
    # record = NOTE (the specific), note = Dementia; note_term "Dementia" is a synonym of note_code.
    fake_dementia_descr = _FakeHermes(
        concepts={NOTE: "Microscopic polyarteritis nodosa (disorder)", _DEM: "Dementia (disorder)"},
        subsumes={(NOTE, _DEM): True},
        descriptions={_DEM: ["Dementia", "Dementia (disorder)"], NOTE: ["Microscopic polyangiitis"]},
    )
    _patch(monkeypatch, client=fake_dementia_descr, jute_client=_FakeJuteClient({
        "record_code": str(NOTE), "record_term": "Microscopic polyangiitis",
        "note_code": str(_DEM), "note_term": "Dementia",  # a real synonym of _DEM
    }))
    v = _executor(_clear_params()).check(dict(_FINDING), _CASE)
    assert v.disproved is True  # synonym passes check2; same-category + record is-a note -> CLEAR


# ─────────────────────────── 4. check 3 CATEGORY ───────────────────────────
def test_category_mismatch_stands_check3(monkeypatch):
    NOTE = 111
    REC = 222
    fake = _FakeHermes(
        concepts={NOTE: "Some disease (disorder)", REC: "Some operation (procedure)"},
        subsumes={},
        descriptions={NOTE: ["Some disease"]},
    )
    _patch(monkeypatch, client=fake, jute_client=_FakeJuteClient({
        "record_code": str(REC), "record_term": "Some operation",
        "note_code": str(NOTE), "note_term": "Some disease",
    }))
    v = _executor(_clear_params()).check(dict(_FINDING), _CASE)
    assert v.disproved is False  # note (disorder) != record (procedure)
    assert "check3" in v.reason and "categor" in v.reason.lower()


# ─────────────────────────── 5. check 7 UPCODE: never cleared ───────────────────────────
def test_upcode_note_strict_descendant_of_record_stands_check7(monkeypatch):
    # note is MORE specific than record: subsumed_by(note, record) True, reverse False.
    fake = _FakeHermes(
        concepts={_ALZ: "Alzheimer's disease (disorder)", _DEM: "Dementia (disorder)"},
        subsumes={(_ALZ, _DEM): True, (_DEM, _ALZ): False},
        descriptions={_ALZ: ["Alzheimer's disease", "Alzheimer's"]},
    )
    # record = Dementia (general), note = Alzheimer's (specific) -> note strict-descendant of record
    _patch(monkeypatch, client=fake, jute_client=_FakeJuteClient({
        "record_code": str(_DEM), "record_term": "Dementia",
        "note_code": str(_ALZ), "note_term": "Alzheimer's",
    }))
    v = _executor(_clear_params()).check(dict(_FINDING), _CASE)
    assert v.disproved is False  # UPCODE is NEVER cleared
    assert "check7" in v.reason and "upcode" in v.reason.lower()


# ─────────────────────────── 6. check 7 DEFER: no is-a either way ───────────────────────────
def test_no_isa_either_way_defers_and_stands(monkeypatch):
    NOTE = 333
    REC = 444
    fake = _FakeHermes(
        concepts={NOTE: "Thing A (disorder)", REC: "Thing B (disorder)"},
        subsumes={(NOTE, REC): False, (REC, NOTE): False},  # unrelated
        descriptions={NOTE: ["Thing A"]},
    )
    _patch(monkeypatch, client=fake, jute_client=_FakeJuteClient({
        "record_code": str(REC), "record_term": "Thing B",
        "note_code": str(NOTE), "note_term": "Thing A",
    }))
    v = _executor(_clear_params()).check(dict(_FINDING), _CASE)
    assert v.disproved is False  # DEFER: advisory relatedness, not cleared
    assert "check7" in v.reason


# ─────────────────────────── 7. drifted arguments_jute_sha256 -> refuse ───────────────────────────
def test_drifted_arguments_jute_sha_refuses_and_stands(monkeypatch):
    fake = _FakeHermes(concepts=_CLEAR_CONCEPTS, subsumes=_CLEAR_SUBSUMES, descriptions=_CLEAR_DESCR)
    _patch(monkeypatch, client=fake, jute_client=_FakeJuteClient(_clear_shape()))
    v = _executor({
        "tool": "hermes_snomed",
        "arguments_jute": _JUTE, "arguments_jute_sha256": "deadbeef" * 8,
    }).check(dict(_FINDING), _CASE)
    assert v.disproved is False  # NEVER grade through a drifted transform
    assert "drift" in v.reason.lower() or "mismatch" in v.reason.lower()


def test_absent_shape_stands(monkeypatch):
    # a shape that will not produce the 4 fields (output None) -> finding stands, no 500
    fake = _FakeHermes(concepts=_CLEAR_CONCEPTS, subsumes=_CLEAR_SUBSUMES)
    _patch(monkeypatch, client=fake, jute_client=_NullShapeJuteClient())
    v = _executor(_clear_params()).check(dict(_FINDING), _CASE)
    assert v.disproved is False


# ─────────────────────────── 8. graceful-absent: tool unavailable / raises mid-battery ─────────────
def test_tool_not_available_is_graceful(monkeypatch):
    _patch(monkeypatch, manifest=None, jute_client=_FakeJuteClient(_clear_shape()))
    v = _executor(_clear_params()).check(dict(_FINDING), _CASE)
    assert v.disproved is False  # finding STANDS when the tool is unavailable


def test_tool_without_stdio_transport_is_graceful(monkeypatch):
    no_mcp = PluginManifest(
        id="hermes_snomed", kind="tool", transport="service", implements="tool.mcp_server",
        service={},  # no mcp.command
    )
    _patch(monkeypatch, manifest=no_mcp, jute_client=_FakeJuteClient(_clear_shape()))
    v = _executor(_clear_params()).check(dict(_FINDING), _CASE)
    assert v.disproved is False


def test_raise_mid_battery_is_graceful(monkeypatch):
    # an McpError OUTSIDE check 1's validity branch (e.g. fully_specified_name) -> finding stands,
    # never a 500, never a silent clear.
    fake = _FakeHermes(
        concepts=_CLEAR_CONCEPTS, subsumes=_CLEAR_SUBSUMES, descriptions=_CLEAR_DESCR,
        error_on="fully_specified_name",
    )
    _patch(monkeypatch, client=fake, jute_client=_FakeJuteClient(_clear_shape()))
    v = _executor(_clear_params()).check(dict(_FINDING), _CASE)
    assert v.disproved is False  # graceful: no clear on error


def test_missing_tool_id_is_inconclusive(monkeypatch):
    _patch(monkeypatch, jute_client=_FakeJuteClient(_clear_shape()))
    v = _executor({"arguments_jute": _JUTE, "arguments_jute_sha256": _JUTE_SHA}).check(
        dict(_FINDING), _CASE
    )
    assert v.disproved is False  # no tool bound -> finding stands
