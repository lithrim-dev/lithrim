"""v1 end-to-end proof: Synthea row -> SOAP note -> WRONG_DOSAGE -> JSONL.

Demonstrates the engine spine. Produces one clean negative and one
injected case for the same encounter, so both labels are anchored to
identical ground truth.

Usage:
    python scripts/generate_proof_case.py [--out examples/proof_case.jsonl]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the project root is on sys.path so `lithrim_bench` imports when
# the script is run directly (no editable install required for the smoke).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lithrim_bench.injectors import WrongDosageInjector
from lithrim_bench.packager import package_case, write_jsonl
from lithrim_bench.synthea_loader import SyntheaCohort
from lithrim_bench.synthesizers.scribe_artifact import synthesize_scribe_artifact
from lithrim_bench.synthesizers.transcript import synthesize_scribe_transcript
from lithrim_bench.taxonomy import load_taxonomy


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--cohort",
        default=Path(__file__).resolve().parent.parent / "data" / "synthea_sample_data_csv_latest",
        type=Path,
    )
    ap.add_argument(
        "--out",
        default=Path(__file__).resolve().parent.parent / "examples" / "proof_case.jsonl",
        type=Path,
    )
    args = ap.parse_args()

    cohort = SyntheaCohort(args.cohort)
    taxonomy = load_taxonomy()

    spec = None
    for pid in cohort.patient_ids():
        candidate = cohort.first_encounter_with_active_medication(pid)
        if candidate is not None and WrongDosageInjector().applies(candidate):
            spec = candidate
            break

    if spec is None:
        sys.exit("no Synthea patient with a parseable medication dose found")

    transcript = synthesize_scribe_transcript(spec)
    artifact = synthesize_scribe_artifact(spec)

    pinned = {
        "generator_version": "lithrim-bench/0.1.0",
        "taxonomy_snapshot": "taxonomy/taxonomy_snapshot.json",
        "synthea_cohort_sha256": spec.provenance.cohort_sha256,
        "injector": "WrongDosageInjector(factor=10.0)",
        "deterministic_synthesis": True,
    }

    clean_case = package_case(
        spec=spec,
        pack="scribe_v1",
        agent_type="scribe",
        transcript=transcript,
        artifacts=[artifact],
        recipe=None,
        taxonomy=taxonomy,
        pinned=pinned,
        clinical_severity="low",
    )

    inj = WrongDosageInjector(factor=10.0).inject(spec, transcript, artifact)
    defect_case = package_case(
        spec=spec,
        pack="scribe_v1",
        agent_type="scribe",
        transcript=inj.transcript,
        artifacts=[inj.artifact],
        recipe=inj.recipe,
        taxonomy=taxonomy,
        pinned=pinned,
        clinical_severity="high",
    )

    write_jsonl([clean_case, defect_case], args.out)
    print(f"wrote {args.out}")
    print(f"  clean negative:  {clean_case['case_id']}")
    print(f"  injected case:   {defect_case['case_id']}")
    print(f"  recipe:          {defect_case['injection_recipe']['safety_flag']} via "
          f"{defect_case['injection_recipe']['mutated_projection']} "
          f"({defect_case['injection_recipe']['pre_value']!r} -> "
          f"{defect_case['injection_recipe']['post_value']!r})")
    print(f"  expected_compliance_verdict: {defect_case['expected_compliance_verdict']}")
    print(f"  expected_artifact_verdict:   {defect_case['expected_artifact_verdict']}")
    print(f"  expected_owner_map:          {defect_case['expected_owner_map']}")


if __name__ == "__main__":
    main()
