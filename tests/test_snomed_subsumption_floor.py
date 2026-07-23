"""SNOMED-SUBSUMPTION-FLOOR-1 — the proactive terminology detector floor.

The mechanism: read the note-vs-record diagnosis codes off the case, ask the SNOMED tool the is-a
direction, and INJECT ``UPCODED_DIAGNOSIS`` when the note is a strict descendant of the record — no
judge flag required. This is the recall mirror of the extraction floor and the answer to "judges are
unreliable at specificity": the check is SME-authored and runs deterministically over the wired tool.

Conservatism is the invariant: no codes, an unreachable tool, or no is-a either way DECLINE
(``conforms=None``); only a strict-descendant note INJECTS (``conforms=False``); a valid
generalisation is ``conforms=True``. The terminology client is injected here so the suite stays
$0/offline.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.verification.snomed_floor import SnomedSubsumptionFloorTool  # noqa: E402
from lithrim_bench.verification.spec import Claim, VerificationSpec  # noqa: E402

JME, EPILEPSY, UNRELATED = 6204001, 84757009, 40733004


class _FakeHermes:
    """A tiny is-a oracle: child -> its ancestors. JME is-a Epilepsy, nothing else related."""

    _ANCESTORS = {JME: {EPILEPSY}}

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def call_tool(self, name: str, args: dict):
        self.calls.append((name, args))
        if name != "subsumed_by":
            raise ValueError(name)
        child, subsumer = args["concept_id"], args["subsumer_id"]
        return {"subsumedBy": child == subsumer or subsumer in self._ANCESTORS.get(child, set())}

    def close(self) -> None:  # noqa: D401
        pass


def _case(note_code, record_code):
    return {
        "case_id": "t",
        "transcript": "...",
        "artifacts": [{"content": "note"}],
        "pinned": {
            "subsumption": {
                "note_child_snomed": note_code,
                "record_parent_snomed": record_code,
            }
        },
    }


def _verify(note_code, record_code, *, client=None, source=None):
    tool = SnomedSubsumptionFloorTool(client=client if client is not None else _FakeHermes())
    claim = Claim(
        claim_type="structural_conformance",
        flag_code="UPCODED_DIAGNOSIS",
        subject="note text",
        locus="",
        source=source if source is not None else _case(note_code, record_code),
    )
    spec = VerificationSpec(
        tool="snomed_subsumption_floor",
        applies_to_flags=("UPCODED_DIAGNOSIS",),
        locus="",
        reference={"tool": "hermes_snomed"},
        version="test/1",
    )
    return tool.verify(claim, spec)


# ── the three-way disposition ─────────────────────────────────────────────────


def test_upcode_note_more_specific_injects():
    """note=JME, record=Epilepsy: the note is more specific than the record supports -> INJECT."""
    res = _verify(JME, EPILEPSY)
    assert res.conforms is False
    assert res.evidence["note_isa_record"] is True
    assert res.evidence["record_isa_note"] is False
    assert "upcode" in res.evidence["reason"]


def test_valid_generalisation_does_not_inject():
    """note=Epilepsy, record=JME: the note is a valid generalisation -> conforms True, no block."""
    res = _verify(EPILEPSY, JME)
    assert res.conforms is True


def test_generalisation_read_from_parent_child_keys():
    """Real generalisation cases pin ``note_parent_snomed`` / ``record_child_snomed`` (the opposite
    key convention from the upcode twin). The floor must read the note/record codes regardless of
    the SME's child/parent labelling and still conclude 'valid generalisation'."""
    source = {
        "case_id": "t",
        "pinned": {
            "subsumption": {
                "note_parent_snomed": EPILEPSY,
                "record_child_snomed": JME,
            }
        },
    }
    res = _verify(None, None, source=source)
    assert res.conforms is True, "note(Epilepsy) is a valid generalisation of record(JME)"


def test_unrelated_codes_decline():
    res = _verify(UNRELATED, EPILEPSY)
    assert res.conforms is None


# ── conservatism: every failure mode declines, never fabricates ───────────────


def test_missing_codes_decline():
    res = _verify(None, None, source={"case_id": "t", "pinned": {}})
    assert res.conforms is None
    assert "no note/record" in res.evidence["reason"]


def test_tool_error_declines():
    class _Boom:
        def call_tool(self, *a, **k):
            raise RuntimeError("hermes unreachable")

        def close(self):
            pass

    res = _verify(JME, EPILEPSY, client=_Boom())
    assert res.conforms is None
    assert "failed" in res.evidence["reason"]


# ── the manifest is honestly deterministic (unlike the extraction floors) ─────


def test_manifest_is_deterministic_and_names_the_tool():
    res = _verify(JME, EPILEPSY)
    assert res.manifest["deterministic"] is True
    assert res.manifest["terminology_tool"] == "hermes_snomed"
    assert res.manifest["tool"] == "snomed_subsumption_floor"


# ── it is wired as a FLOOR (inject) executor, not a suppress validator ────────


def test_registered_as_a_core_floor_executor():
    """Registered in the CORE floor registry (available to every pack, incl. clinverdict), and it
    is a FLOOR (detector/inject) executor, NOT a suppress validator."""
    from lithrim_bench.harness import grounding as G

    floor = set(G.floor_executors())
    suppress = set(G.suppress_executors())
    assert "snomed_subsumption_floor" in floor, "must be a FLOOR (detector) executor"
    assert "snomed_subsumption_floor" not in suppress, "must NOT be a suppress validator"


def test_floor_contract_type_is_recognized():
    from lithrim_bench.harness import grounding as G

    assert "snomed_subsumption_floor" in G.floor_contract_types()
