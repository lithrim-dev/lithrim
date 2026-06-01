"""Mutation coverage — measure how COMPLETE a by-construction oracle / validator is.

Motivation (the timestamp bug, engagement-3): the bench ACCEPTED a validator whose
`timestamp` check was effectively first-char-only, because the pack tested that datatype
with exactly ONE example that didn't exercise the bug. One-example-per-defect-class is the
hole. The bench's guarantee is only as good as the oracle's coverage — so "is the oracle
complete?" must become a measured NUMBER, not faith.

This is the **mutate-the-DATA** direction: from a clean artifact + a field-type spec, generate
a BATTERY of by-construction defect-mutants per field (many, adversarial — not one), apply the
validator, and any defect-mutant the validator PASSES is a SURVIVOR = a concrete, already-labeled
blind spot. The mutation score = fraction of defect-mutants the validator catches.

The mutants are free to score (`test-template`, no LLM). The reusable asset is the OPERATOR set
(below): one date-datatype operator serves birthDate, effectiveDateTime, timestamp, so it
compounds across domains.

Scope of this first slice: charset/structural operators (presence, enum, datatype-shape,
cardinality). SEMANTIC-RANGE operators (month>12, multi-dot decimal, cross-field invariants)
need range validators beyond the charset idiom and are a DEFERRED operator class — noted, not
silently omitted. Mutation coverage is a measurable LOWER BOUND on completeness, not a proof.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from .jute_dspy import verdict_for


def _without(d: dict, field: str) -> dict:
    a = copy.deepcopy(d)
    a.pop(field, None)
    return a


def _with(d: dict, field: str, value: Any) -> dict:
    a = copy.deepcopy(d)
    a[field] = value
    return a


def _datatype_malformations(datatype: str) -> list[tuple[Any, str]]:
    """Adversarial values a CHARSET datatype check should reject. `legal_prefix_then_junk`
    is the one that catches the anchored-regex / first-char-only bug class."""
    if datatype == "decimal":
        return [("abc", "illegal_first_char"), ("12!!34", "legal_prefix_then_junk"), ("", "empty")]
    if datatype in ("date", "datetime"):
        return [
            ("not-a-date", "illegal_first_char"),
            ("2026!!junk", "legal_prefix_then_junk"),
            ("", "empty"),
        ]
    return [("!!bad", "illegal_first_char"), ("", "empty")]


def field_mutants(clean: dict, spec: dict) -> list[dict]:
    """Yield the by-construction mutant battery for ONE field spec.

    spec = {"field", "kind": "presence"|"enum"|"datatype"|"cardinality",
            "required": bool, "values": [...] (enum), "datatype": "date"|"datetime"|"decimal"}
    Each mutant: {label, field, op, value, artifact, expected} where expected is the verdict a
    CORRECT validator must return (BLOCK for a defect; PASS for the optional-strip control).
    """
    field = spec["field"]
    required = spec.get("required", True)
    kind = spec["kind"]
    out: list[dict] = []

    def add(op, value, artifact, expected):
        out.append(
            {
                "label": f"{field}:{op}",
                "field": field,
                "op": op,
                "value": value,
                "artifact": artifact,
                "expected": expected,
            }
        )

    # presence / absence (every field)
    if required:
        add("strip", "<absent>", _without(clean, field), "BLOCK")
        add("null", None, _with(clean, field, None), "BLOCK")
    else:
        add("strip", "<absent>", _without(clean, field), "PASS")  # optional-field FP control

    if kind == "enum":
        vals = spec["values"]
        cands = [
            ("not_in_set", "__bogus__"),
            ("empty", ""),
            ("near_miss", f"{vals[0]}X"),
            ("numeric", 123),
        ]
        cv = str(vals[0]).swapcase()
        if cv not in vals:
            cands.append(("case_variant", cv))
        for op, v in cands:
            add(op, v, _with(clean, field, v), "BLOCK")
    elif kind == "datatype":
        for v, op in _datatype_malformations(spec.get("datatype", "string")):
            add(op, v, _with(clean, field, v), "BLOCK")
    elif kind == "cardinality":
        for op, v in [("empty_array", []), ("scalar_not_array", "scalar")]:
            add(op, v, _with(clean, field, v), "BLOCK")

    return out


def generate_mutants(clean: dict, field_specs: list[dict]) -> list[dict]:
    mutants: list[dict] = []
    for spec in field_specs:
        mutants.extend(field_mutants(clean, spec))
    return mutants


def _mutant_to_case(m: dict, pack_id: str) -> dict:
    return {
        "case_id": f"{pack_id}_{m['label']}",
        "pack": pack_id,
        "expected_structural_verdict": m["expected"],
        "artifacts": [{"type": "mutant", "content": json.dumps(m["artifact"])}],
        "injection_recipes": [
            {"defect_type": f"mutation:{m['op']}", "mutated_field_or_span": m["field"]}
        ],
    }


def mutants_to_cases(
    clean: dict, field_specs: list[dict], *, pack_id: str = "mutation_battery"
) -> list[dict]:
    """Convert the mutant battery into PACK-SHAPED cases (`expected_structural_verdict` +
    `artifacts[0].content`), so the EXISTING bench loop (`score_template` / `bench_accept` /
    `feedback_from` / `build_generator`) consumes them unchanged. A mutant IS just another
    by-construction case.

    WARNING (verified): gating a generator on `pack + FULL battery` from a BLANK start does NOT
    converge — the model is overwhelmed authoring a validator robust to every adversarial input
    at once and returns a broadly-erroring template (88% -> 4% in the transaction run). Use this
    to MEASURE (mutation_coverage), and `survivor_cases` + a SEEDED generator to HARDEN
    incrementally (add only what slipped through, refine the known-good validator)."""
    return [_mutant_to_case(m, pack_id) for m in generate_mutants(clean, field_specs)]


def survivor_cases(
    clean: dict,
    field_specs: list[dict],
    survivors: list[dict],
    *,
    pack_id: str = "mutation_survivors",
) -> list[dict]:
    """Pack-shaped cases for just the SURVIVING mutants — the surgical hardening input: add
    only what the current validator missed, then refine a SEEDED generator against
    `pack + these` so it makes a minimal edit instead of re-deriving from scratch."""
    labels = {s["label"] for s in survivors}
    return [
        _mutant_to_case(m, pack_id)
        for m in generate_mutants(clean, field_specs)
        if m["label"] in labels
    ]


def valid_variations(clean: dict, field_specs: list[dict]) -> list[dict]:
    """The PRECISION operator — mutate the clean artifact to OTHER VALID values per field
    (all expected PASS), the symmetric counterpart to the defect battery. Catches the
    precision regressions a single fixed clean case misses (e.g. hardening that blocks a
    valid value shape it was not trained on). Each item: {label, field, op, value, artifact,
    expected="PASS"}."""
    out: list[dict] = []

    def add(field, tag, value, artifact):
        out.append(
            {
                "label": f"{field}:valid:{tag}",
                "field": field,
                "op": f"valid:{tag}",
                "value": value,
                "artifact": artifact,
                "expected": "PASS",
            }
        )

    for spec in field_specs:
        field = spec["field"]
        kind = spec["kind"]
        dt = spec.get("datatype")
        if kind == "enum":
            for v in spec["values"][1:]:  # every OTHER valid code (clean uses values[0])
                add(field, str(v), v, _with(clean, field, v))
        elif kind == "datatype" and dt == "datetime":
            for v in ("2027-01-15T23:59:59Z", "2026-05-30T09:00:00+05:30"):
                add(field, v, v, _with(clean, field, v))
        elif kind == "datatype" and dt == "date":
            for v in ("2025-01-01", "1999-12-31"):
                add(field, v, v, _with(clean, field, v))
        elif kind == "datatype" and dt == "decimal":
            for v in ("0.99", "1000000.00", "5"):
                add(field, v, v, _with(clean, field, v))
        if not spec.get("required", True):
            add(field, "absent", "<absent>", _without(clean, field))
    return out


def valid_variation_cases(
    clean: dict, field_specs: list[dict], *, pack_id: str = "valid_variation"
) -> list[dict]:
    """Pack-shaped (expected PASS) cases for the valid variations — the PRECISION half of the
    JOINT gate. Because a blocked PASS-case counts as an FP, adding these to the gate makes the
    EXISTING `bench_accept` (0 FP AND 0 ERR AND all defects caught) a joint recall+precision gate
    with no change to the scorer."""
    return [_mutant_to_case(m, pack_id) for m in valid_variations(clean, field_specs)]


def joint_coverage(client: Any, template: str, clean: dict, field_specs: list[dict]) -> dict:
    """The corrected oracle-completeness number — a RECALL/PRECISION PAIR, not a single %.

    recall    = adversarial defect-mutants caught / total   (survivors = the blind spots)
    precision = valid variations passed / total             (precision_breaks = the regressions)
    The two trade off; a complete oracle must measure both (the mutation battery alone hid the
    surgical run's precision regression — its only valid-timestamp control was 'absent')."""

    def _row(m, verdict):
        return {
            "label": m["label"],
            "field": m["field"],
            "op": m["op"],
            "value": m["value"],
            "expected": m["expected"],
            "verdict": verdict,
        }

    defect_rows, valid_rows = [], []
    for m in generate_mutants(clean, field_specs):
        verdict, _f, _e = verdict_for(client, template, m["artifact"])
        (defect_rows if m["expected"] == "BLOCK" else valid_rows).append(_row(m, verdict))
    for m in valid_variations(clean, field_specs):
        verdict, _f, _e = verdict_for(client, template, m["artifact"])
        valid_rows.append(_row(m, verdict))

    survivors = [r for r in defect_rows if r["verdict"] != "BLOCK"]
    precision_breaks = [r for r in valid_rows if r["verdict"] != "PASS"]
    return {
        "recall": (len(defect_rows) - len(survivors)) / len(defect_rows) if defect_rows else 1.0,
        "survivors": survivors,
        "defects": len(defect_rows),
        "precision": (len(valid_rows) - len(precision_breaks)) / len(valid_rows)
        if valid_rows
        else 1.0,
        "precision_breaks": precision_breaks,
        "valids": len(valid_rows),
        "complete": len(survivors) == 0 and len(precision_breaks) == 0,
    }


def mutation_coverage(client: Any, template: str, clean: dict, field_specs: list[dict]) -> dict:
    """Apply `template` to the by-construction mutant battery and score completeness.

    Returns {score, killed, defects, survivors, fp, rows}:
      - score      = killed defect-mutants / total defect-mutants (the mutation score)
      - survivors  = defect-mutants the validator PASSED or ERR'd (the actionable blind spots,
                     each already labeled by construction)
      - fp         = optional-strip controls the validator wrongly BLOCKED
    """
    rows = []
    for m in generate_mutants(clean, field_specs):
        verdict, _failed, _err = verdict_for(client, template, m["artifact"])
        rows.append(
            {**{k: m[k] for k in ("label", "field", "op", "value", "expected")}, "verdict": verdict}
        )

    defects = [r for r in rows if r["expected"] == "BLOCK"]
    controls = [r for r in rows if r["expected"] == "PASS"]
    killed = [r for r in defects if r["verdict"] == "BLOCK"]
    survivors = [r for r in defects if r["verdict"] != "BLOCK"]  # passed (or ERR'd) a known defect
    fp = [r for r in controls if r["verdict"] == "BLOCK"]
    return {
        "score": len(killed) / len(defects) if defects else 1.0,
        "killed": len(killed),
        "defects": len(defects),
        "survivors": survivors,
        "fp": fp,
        "rows": rows,
    }
