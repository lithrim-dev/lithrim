"""Import ``lithrim-backend`` demo-dataset rows onto the bench as second-class cases.

The backend authored its ``demo_dataset/*.jsonl`` scenarios by hand (a transcript +
artifact + ``expected_*`` labels + a ``notes`` justification), NOT through the bench
injector. They carry no structured ``injection_recipe``, so they are EXEMPT from the
strict by-construction admissibility lint (``packager.package_case`` raises on a recipe
whose flag is unknown; these rows have no recipe to check). They are graded against the
labels the backend provided, and live in a SEPARATE ``examples/imported_demo_*.jsonl``
corpus stamped ``ground_truth_basis="imported_demo"`` so they are never confused with
first-class bench rows.

What survives the import is the TAXONOMY contract: every ``expected_safety_flags`` code
is linted against the frozen snapshot (:meth:`Taxonomy.is_known`). A code that does not
resolve is QUARANTINED — dropped from the row and surfaced via ``quarantined_flags`` —
because the snapshot is the cross-repo contract and is never edited here to admit a
drifted backend code (that is a separate ``scripts/snapshot_taxonomy.py`` decision).
"""

from __future__ import annotations

from typing import Any

from lithrim_bench.packager import _split_for
from lithrim_bench.taxonomy import Taxonomy, load_taxonomy

GROUND_TRUTH_BASIS = "imported_demo"


def load_backend_record(
    row: dict[str, Any], *, pack: str, taxonomy: Taxonomy | None = None
) -> dict[str, Any]:
    """Map one backend demo-dataset row to a second-class bench case row.

    ``pack`` is the domain bucket (e.g. ``"scribe"``); it namespaces the synthesized
    ``case_id`` and selects the output ``imported_demo_<pack>.jsonl`` file. ``taxonomy``
    defaults to the frozen snapshot; inject one in tests.

    The returned row is grade-path-ready (it carries ``case_id``/``agent_type``/
    ``transcript``/``artifacts``/``expected_compliance_verdict``/``expected_safety_flags``
    — everything ``LocalPipelineBackend._build_request`` + ``run_eval.run`` read) plus
    the second-class provenance fields. ``quarantined_flags`` lists any
    ``expected_safety_flags`` code that failed the taxonomy lint (empty when all resolve).
    """
    tax = taxonomy or load_taxonomy()

    scenario_id = row.get("scenario_id") or row.get("id") or row.get("case_id")
    if not scenario_id:
        raise ValueError("backend row has no scenario_id/id/case_id to key on")

    raw_flags = list(row.get("expected_safety_flags") or [])
    kept_flags = sorted({f for f in raw_flags if tax.is_known(f)})
    quarantined = sorted({f for f in raw_flags if not tax.is_known(f)})

    # The backend rows omit allergies (only demographics/conditions/active_medications);
    # default to [] so the patient_profile shape matches the bench-native rows.
    profile = dict(row.get("patient_profile") or {})
    profile.setdefault("allergies", [])

    case_id = f"imported_{pack}_{scenario_id}"
    return {
        "case_id": case_id,
        "pack": pack,
        "agent_type": row.get("agent_type"),
        "ground_truth_basis": GROUND_TRUTH_BASIS,
        # Synthea-generated demo data — synthetic by construction, no PHI (A1 asserts it).
        "synthetic": True,
        "patient_profile": profile,
        "transcript": row.get("transcript", "") or "",
        "artifacts": row.get("artifacts") or [],
        # No by-construction recipe — this is what makes the row second-class.
        "injection_recipes": [],
        "expected_compliance_verdict": row.get("expected_compliance_verdict"),
        "expected_artifact_verdict": row.get("expected_artifact_verdict"),
        "expected_safety_flags": kept_flags,
        "quarantined_flags": quarantined,
        "clean_negative": not kept_flags,
        "split": _split_for(case_id),
        "label_justification": row.get("notes") or "",
        "source_scenario_id": scenario_id,
    }
