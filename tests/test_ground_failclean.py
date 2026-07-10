"""ground() fail-clean: a raising suppress executor leaves the finding STANDING, never 500s.

A service-transport suppress executor (one composing over an out-of-process tool or service) can
raise if that service is unreachable. ``ground()`` must absorb that — the finding STANDS (never
cleared by silence) and the grade does not abort. CE-clean: a fake raising executor, no pack, no
external service, no network.
"""

from __future__ import annotations

from lithrim_bench.harness import grounding
from lithrim_bench.harness.ontology import from_dict


def _ont_with(contract_type: str):
    return from_dict(
        {
            "ontology_version": "failclean/1",
            "domain": "test",
            "flags": [],
            "questions": [],
            "verification_contracts": [
                {
                    "flag_code": "X",
                    "question": "?",
                    "contract_type": contract_type,
                    "params": {},
                    "version": f"{contract_type}/1",
                }
            ],
            "severity_map": {
                "weights": {"HIGH": 1.0},
                "block_at_or_above": 0.5,
                "warn_above": 0.0,
            },
        }
    )


def _result():
    return {"verdict": "BLOCK", "findings": [{"code": "X", "severity": "HIGH", "detail": "fp?"}]}


class _Boom:
    def __init__(self, decl):
        self._decl = decl

    def check(self, finding, case):
        raise RuntimeError("terminology server unreachable")


class _CleanVerdict:
    disproved = True
    reason = "grounded"
    evidence = None


class _Clean:
    def __init__(self, decl):
        self._decl = decl

    def check(self, finding, case):
        return _CleanVerdict()


def test_raising_suppress_executor_leaves_finding_standing(monkeypatch):
    """The fail-clean guard: a raise during contract.check() is absorbed — the finding STANDS
    (re-scored to BLOCK), nothing is suppressed, and the unavailability is marked for audit."""
    monkeypatch.setattr(grounding, "suppress_executors", lambda: {"boom": _Boom})
    g = grounding.ground(_result(), {}, ontology=_ont_with("boom"))
    assert g.verdict == "BLOCK"  # did NOT abort/500; the finding stands
    assert g.suppressed == []
    assert [f["code"] for f in g.active] == ["X"]
    assert any("_grounding_error" in f for f in g.active)


def test_non_raising_suppress_still_suppresses(monkeypatch):
    """Non-vacuity the other way: a normally-returning suppress executor is UNAFFECTED by the
    guard — it still suppresses (BLOCK -> PASS)."""
    monkeypatch.setattr(grounding, "suppress_executors", lambda: {"clean": _Clean})
    g = grounding.ground(_result(), {}, ontology=_ont_with("clean"))
    assert g.verdict == "PASS"
    assert {s["finding"]["code"] for s in g.suppressed} == {"X"}
    assert g.active == []
