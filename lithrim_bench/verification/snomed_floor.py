"""SNOMED-SUBSUMPTION-FLOOR-1 — the PROACTIVE terminology detector floor.

The gap this closes: ``snomed_battery`` is a VALIDATOR (suppress plane) — it confirms or clears a
judge's *existing* UPCODED flag. But recognising that a coded diagnosis is more specific than the
record supports (a strict-descendant code under a broader recorded one) is exactly the terminology
reasoning LLM judges are unreliable at, so the flag is usually never raised and the validator never
fires. This floor DETECTS the upcode directly: it reads the note-vs-record diagnosis codes off the
case, asks the terminology tool the is-a direction, and INJECTS ``UPCODED_DIAGNOSIS`` when the note
code is a STRICT DESCENDANT of the record code — no judge flag required.

It is the recall mirror of the extraction floor: SME authors the check once, it runs deterministically
over the wired terminology tool, and catches the whole defect family. The is-a lookup is exact
(terminology subsumption), so the manifest is honestly ``deterministic: True`` (extraction floors are
``False``). Conservative by construction: no codes, an unreachable tool, or no is-a relationship in
either direction all DECLINE (``conforms=None``) rather than fabricate a block. A valid generalisation
(record is-a note) returns ``conforms=True`` (never an upcode). The terminology client is injectable
so tests are $0/offline; live, it opens the pack-declared MCP tool via the plugin registry.
"""

from __future__ import annotations

import contextlib
from typing import Any

from .spec import Claim, VerificationResult, VerificationSpec
from .tools import VerificationTool

TOOL_SNOMED_SUBSUMPTION_FLOOR = "snomed_subsumption_floor"
_ISA_CALL = "subsumed_by"


class SnomedSubsumptionFloorTool(VerificationTool):
    """Floor: inject the pinned ``inject_flag_code`` (an upcode) when the note diagnosis code is a
    strict descendant of the record diagnosis code per the terminology tool's is-a hierarchy.

    reference = {"tool": <terminology tool id, e.g. hermes_snomed>, source_path?}. The codes are
    read off the case's ``pinned.subsumption`` (``note_child_snomed`` / ``record_parent_snomed``,
    the by-construction diagnosis pair). ``client`` is injectable for offline tests; live it is
    resolved from the tool id via the plugin registry."""

    name = TOOL_SNOMED_SUBSUMPTION_FLOOR

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def _open_client(self, tool_id: str) -> Any:
        from lithrim_bench.harness import plugins

        from .mcp_client import McpStdioClient

        manifest = plugins.resolve_tool(tool_id)
        if manifest is None:
            raise RuntimeError(f"terminology tool {tool_id!r} not available")
        mcp = (manifest.service or {}).get("mcp") or {}
        if not mcp.get("command"):
            raise RuntimeError(f"terminology tool {tool_id!r} has no stdio MCP transport")
        return McpStdioClient(command=mcp.get("command"), args=mcp.get("args", []))

    @staticmethod
    def _codes(source: dict[str, Any]) -> tuple[Any, Any]:
        """The NOTE diagnosis code and the RECORD diagnosis code, read regardless of the SME's
        child/parent key labelling — the floor must not trust the pre-label (that IS the direction
        it exists to resolve): a case may pin ``note_child_snomed`` (an upcode framing) or
        ``note_parent_snomed`` (a generalisation framing); either way we want the note's actual code
        and the record's actual code, then the terminology tool decides which is more specific."""
        sub = ((source or {}).get("pinned") or {}).get("subsumption") or {}
        note = (
            sub.get("note_child_snomed")
            or sub.get("note_parent_snomed")
            or sub.get("note_snomed")
            or sub.get("note_code")
        )
        record = (
            sub.get("record_parent_snomed")
            or sub.get("record_child_snomed")
            or sub.get("record_snomed")
            or sub.get("record_code")
        )
        return note, record

    def verify(self, claim: Claim, spec: VerificationSpec) -> VerificationResult:
        ref = spec.reference
        tool_id = ref.get("tool") or "hermes_snomed"
        manifest = {
            "tool": self.name,
            # the is-a lookup is EXACT (terminology subsumption), so unlike the bounded-extraction
            # floors this one is honestly deterministic.
            "deterministic": True,
            "terminology_tool": tool_id,
            "check": "is-a subsumption direction (note strict-descendant of record = upcode)",
            "spec_version": spec.version,
        }
        note_code, record_code = self._codes(claim.source or {})
        if note_code in (None, "") or record_code in (None, ""):
            return VerificationResult(
                conforms=None,
                evidence={"reason": "no note/record codes on the case; cannot ground"},
                manifest=manifest,
            )

        client, opened = self._client, False
        if client is None:
            try:
                client = self._open_client(tool_id)
                opened = True
            except Exception as exc:  # noqa: BLE001 — tool unavailable → decline, never a 500
                return VerificationResult(
                    conforms=None,
                    evidence={"reason": f"terminology tool unavailable ({exc}); declining"},
                    manifest=manifest,
                )
        try:
            nc, rc = int(note_code), int(record_code)
            note_isa_record = bool(
                (client.call_tool(_ISA_CALL, {"concept_id": nc, "subsumer_id": rc}) or {}).get(
                    "subsumedBy"
                )
            )
            record_isa_note = bool(
                (client.call_tool(_ISA_CALL, {"concept_id": rc, "subsumer_id": nc}) or {}).get(
                    "subsumedBy"
                )
            )
        except Exception as exc:  # noqa: BLE001 — a lookup failure declines, never fabricates
            return VerificationResult(
                conforms=None,
                evidence={"reason": f"terminology lookup failed ({exc}); cannot ground"},
                manifest=manifest,
            )
        finally:
            if opened:
                with contextlib.suppress(Exception):
                    client.close()

        evidence: dict[str, Any] = {
            "note_code": nc,
            "record_code": rc,
            "note_isa_record": note_isa_record,
            "record_isa_note": record_isa_note,
        }
        if note_isa_record and not record_isa_note:
            evidence["reason"] = (
                "note diagnosis is a STRICT DESCENDANT of the record diagnosis "
                "(more specific than the record supports) = upcode"
            )
            return VerificationResult(conforms=False, evidence=evidence, manifest=manifest)
        if record_isa_note:
            evidence["reason"] = (
                "record diagnosis is-a note diagnosis (note is a valid generalisation); not an upcode"
            )
            return VerificationResult(conforms=True, evidence=evidence, manifest=manifest)
        evidence["reason"] = "no is-a relationship in either direction; cannot determine upcode"
        return VerificationResult(conforms=None, evidence=evidence, manifest=manifest)
