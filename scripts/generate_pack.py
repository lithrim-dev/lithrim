"""Generate a deterministic pack of N scribe cases against a Synthea cohort.

Honors the eval-spec §3.1 design matrix: clean_negative / single-defect
/ multi-defect (near-miss deferred to phase 2). Mix is configurable;
defaults are 40% clean, 50% single-defect, 10% multi-defect.

Walks the cohort in sorted (patient_id, encounter_start) order, building
EncounterSpec lazily; assigns a slot in the design matrix based on
deterministic-seeded shuffling of the slot list so the matrix is exactly
balanced even at small N.

Usage:
    python scripts/generate_pack.py --size 100 --out out/scribe_pack_v1.jsonl

Outputs:
    out/scribe_pack_v1.jsonl                 — the cases
    out/scribe_pack_v1.design_matrix.md      — markdown table of what's in the pack
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lithrim_bench.encounter_spec import EncounterSpec
from lithrim_bench.injectors import (
    ALL_INJECTORS,
    DefectInjector,
)
from lithrim_bench.packager import package_case, write_jsonl
from lithrim_bench.synthea_loader import SyntheaCohort
from lithrim_bench.synthesizers.scribe_artifact import synthesize_scribe_artifact
from lithrim_bench.synthesizers.transcript import synthesize_scribe_transcript
from lithrim_bench.taxonomy import load_taxonomy


def _walk_specs(cohort: SyntheaCohort) -> Iterator[EncounterSpec]:
    for pid in cohort.patient_ids():
        spec = cohort.first_encounter_with_active_medication(pid)
        if spec is not None:
            yield spec


def _build_slot_plan(size: int, mix: dict[str, float], seed: int) -> list[str]:
    counts = {
        slot: max(0, round(size * proportion))
        for slot, proportion in mix.items()
    }
    over = sum(counts.values()) - size
    if over != 0:
        order = sorted(counts.keys(), key=lambda k: -counts[k] if over > 0 else counts[k])
        counts[order[0]] -= over
    plan: list[str] = []
    for slot, n in counts.items():
        plan.extend([slot] * n)
    rng = random.Random(seed)
    rng.shuffle(plan)
    return plan


def _injectors_for_spec(spec: EncounterSpec) -> list[DefectInjector]:
    return [cls() for cls in ALL_INJECTORS if cls().applies(spec)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--cohort",
        default=Path(__file__).resolve().parent.parent / "data" / "synthea_sample_data_csv_latest",
        type=Path,
    )
    ap.add_argument("--pack", default="scribe_v1")
    ap.add_argument("--size", type=int, default=50)
    ap.add_argument(
        "--mix",
        default="clean=0.4,single=0.5,multi=0.1",
        help="comma-separated slot=proportion (e.g. clean=0.5,single=0.4,multi=0.1)",
    )
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--out",
        default=Path(__file__).resolve().parent.parent / "out" / "scribe_pack_v1.jsonl",
        type=Path,
    )
    args = ap.parse_args()

    mix = {k: float(v) for k, v in (kv.split("=") for kv in args.mix.split(","))}
    if abs(sum(mix.values()) - 1.0) > 0.001:
        sys.exit(f"--mix proportions must sum to 1.0; got {sum(mix.values())}")

    plan = _build_slot_plan(args.size, mix, args.seed)
    print(f"slot plan: {Counter(plan)}")

    cohort = SyntheaCohort(args.cohort)
    taxonomy = load_taxonomy()
    rng = random.Random(args.seed)

    pinned_base = {
        "generator_version": "lithrim-bench/0.1.0",
        "pack": args.pack,
        "taxonomy_snapshot": "taxonomy/taxonomy_snapshot.json",
        "seed": args.seed,
        "mix": args.mix,
        "deterministic_synthesis": True,
    }

    rows: list[dict] = []
    matrix_entries: list[tuple[str, str, str, list[str]]] = []
    skipped: list[str] = []

    spec_iter = _walk_specs(cohort)
    for slot in plan:
        spec = next(spec_iter, None)
        while spec is not None:
            applicable = _injectors_for_spec(spec)
            if slot == "clean":
                break
            if slot == "single" and applicable:
                break
            if slot == "multi" and len(applicable) >= 2:
                break
            spec = next(spec_iter, None)
        if spec is None:
            skipped.append(slot)
            continue

        applicable = _injectors_for_spec(spec)
        transcript = synthesize_scribe_transcript(spec)
        artifact = synthesize_scribe_artifact(spec)
        pinned = {**pinned_base, "synthea_cohort_sha256": spec.provenance.cohort_sha256}

        recipes = []
        if slot == "single":
            inj = rng.choice(applicable)
            result = inj.inject(spec, transcript, artifact)
            transcript = result.transcript
            artifact = result.artifact
            recipes = [result.recipe]
            pinned["injectors"] = [type(inj).__name__]
        elif slot == "multi":
            chosen = rng.sample(applicable, 2)
            for inj in chosen:
                result = inj.inject(spec, transcript, artifact)
                transcript = result.transcript
                artifact = result.artifact
                recipes.append(result.recipe)
            pinned["injectors"] = [type(inj).__name__ for inj in chosen]

        row = package_case(
            spec=spec,
            pack=args.pack,
            agent_type="scribe",
            transcript=transcript,
            artifacts=[artifact],
            recipes=recipes,
            taxonomy=taxonomy,
            pinned=pinned,
        )
        rows.append(row)
        matrix_entries.append((
            row["case_id"],
            slot,
            row["expected_compliance_verdict"],
            row["expected_safety_flags"],
        ))

    write_jsonl(rows, args.out)

    matrix_path = args.out.with_suffix(".design_matrix.md")
    lines = [
        f"# {args.pack} design matrix",
        "",
        f"- seed: {args.seed}",
        f"- requested: {args.size}",
        f"- produced: {len(rows)}",
        f"- mix: {dict(Counter(slot for _, slot, _, _ in matrix_entries))}",
        f"- skipped (cohort exhausted): {Counter(skipped)}" if skipped else "- skipped: none",
        "",
        "| case_id | slot | verdict | flags |",
        "|---|---|---|---|",
    ]
    for case_id, slot, verdict, flags in matrix_entries:
        lines.append(f"| `{case_id}` | {slot} | {verdict} | {', '.join(flags) or '(none)'} |")
    matrix_path.write_text("\n".join(lines) + "\n")

    print(f"wrote {len(rows)} rows -> {args.out}")
    print(f"wrote design matrix -> {matrix_path}")
    if skipped:
        print(f"WARN: {len(skipped)} cases skipped: {Counter(skipped)}")


if __name__ == "__main__":
    main()
