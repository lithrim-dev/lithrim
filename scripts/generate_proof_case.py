"""v1 end-to-end proof: Synthea row -> SOAP note -> defect injection -> JSONL.

Demonstrates the engine spine. Produces one clean negative plus one
injected case per available injector, all anchored to the same Synthea
encounter where possible (so labels share identical ground truth).

Patient selection finds the FIRST Synthea encounter for which all four
injectors apply. If no single encounter satisfies all four, each
unsatisfied injector is run against its own best-fit encounter (and the
ground-truth alignment is per-injector instead).

Usage:
    python scripts/generate_proof_case.py [--out examples/proof_case.jsonl]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lithrim_bench.encounter_spec import EncounterSpec
from lithrim_bench.injectors import (
    ALL_INJECTORS,
    DefectInjector,
    FabricatedHistoryInjector,
    MissingAllergyInjector,
    ValueMismatchInjector,
    WrongDosageInjector,
)
from lithrim_bench.packager import package_case, write_jsonl
from lithrim_bench.synthea_loader import SyntheaCohort
from lithrim_bench.synthesizers.scribe_artifact import synthesize_scribe_artifact
from lithrim_bench.synthesizers.transcript import synthesize_scribe_transcript
from lithrim_bench.taxonomy import load_taxonomy


def _find_spec_for(cohort: SyntheaCohort, injectors: list[DefectInjector]) -> EncounterSpec | None:
    for pid in cohort.patient_ids():
        spec = cohort.first_encounter_with_active_medication(pid)
        if spec is None:
            continue
        if all(inj.applies(spec) for inj in injectors):
            return spec
    return None


def _best_fit_spec(cohort: SyntheaCohort, injector: DefectInjector) -> EncounterSpec | None:
    for pid in cohort.patient_ids():
        spec = cohort.first_encounter_with_active_medication(pid)
        if spec is not None and injector.applies(spec):
            return spec
    return None


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

    injectors: list[DefectInjector] = [
        WrongDosageInjector(),
        MissingAllergyInjector(),
        FabricatedHistoryInjector(),
        ValueMismatchInjector(),
    ]

    shared_spec = _find_spec_for(cohort, injectors)
    if shared_spec is not None:
        print(f"shared anchor encounter: {shared_spec.encounter.encounter_id} "
              f"(patient {shared_spec.demographics.patient_id})")
    else:
        print("no single encounter satisfies all injectors; using per-injector best fit")

    pinned = {
        "generator_version": "lithrim-bench/0.1.0",
        "taxonomy_snapshot": "taxonomy/taxonomy_snapshot.json",
        "deterministic_synthesis": True,
    }

    rows: list[dict] = []
    seen_clean_encounters: set[str] = set()

    for injector in injectors:
        spec = shared_spec if shared_spec is not None else _best_fit_spec(cohort, injector)
        if spec is None:
            print(f"  SKIP {type(injector).__name__}: no applicable Synthea encounter")
            continue
        transcript = synthesize_scribe_transcript(spec)
        artifacts = [synthesize_scribe_artifact(spec)]

        if spec.encounter.encounter_id not in seen_clean_encounters:
            seen_clean_encounters.add(spec.encounter.encounter_id)
            rows.append(
                package_case(
                    spec=spec,
                    pack="scribe_v1",
                    agent_type="scribe",
                    transcript=transcript,
                    artifacts=artifacts,
                    recipes=[],
                    taxonomy=taxonomy,
                    pinned={**pinned, "synthea_cohort_sha256": spec.provenance.cohort_sha256},
                )
            )

        result = injector.inject(spec, transcript, artifacts)
        row = package_case(
            spec=spec,
            pack="scribe_v1",
            agent_type="scribe",
            transcript=result.transcript,
            artifacts=result.artifacts,
            recipes=[result.recipe],
            taxonomy=taxonomy,
            pinned={**pinned, "synthea_cohort_sha256": spec.provenance.cohort_sha256,
                    "injector": type(injector).__name__},
        )
        rows.append(row)
        print(f"  {type(injector).__name__}: {row['case_id']}")
        print(f"    flag={result.recipe.safety_flag}  "
              f"verdict={row['expected_compliance_verdict']}  "
              f"artifact={row['expected_artifact_verdict']}")
        print(f"    pre={result.recipe.pre_value!r} -> post={result.recipe.post_value!r}")

    write_jsonl(rows, args.out)
    clean = sum(1 for r in rows if r["clean_negative"])
    print(f"\nwrote {len(rows)} rows ({clean} clean, {len(rows) - clean} injected) to {args.out}")


if __name__ == "__main__":
    main()
