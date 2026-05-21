"""Generate a deterministic pack of N cases against a Synthea cohort.

Dispatches via lithrim_bench.packs.PACKS: pick `--pack scribe_v1`,
`scheduling_v1`, etc. Honors the eval-spec §3.1 design matrix
(clean / single-defect / multi-defect; near-miss deferred).

Usage:
    python scripts/generate_pack.py --pack scribe_v1 --size 50
    python scripts/generate_pack.py --pack scheduling_v1 --size 30

Outputs:
    out/<pack>.jsonl                   — the cases
    out/<pack>.design_matrix.md        — markdown table of what's in the pack
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
from lithrim_bench.injectors import DefectInjector
from lithrim_bench.packager import package_case, write_jsonl
from lithrim_bench.packs import PACKS, PackDefinition
from lithrim_bench.synthea_loader import SyntheaCohort
from lithrim_bench.taxonomy import load_taxonomy


def _walk_specs(cohort: SyntheaCohort, requires_med: bool) -> Iterator[EncounterSpec]:
    for pid in cohort.patient_ids():
        if requires_med:
            spec = cohort.first_encounter_with_active_medication(pid)
        else:
            spec = cohort.first_encounter(pid)
        if spec is not None:
            yield spec


def _build_slot_plan(size: int, mix: dict[str, float], seed: int) -> list[str]:
    counts = {slot: max(0, round(size * p)) for slot, p in mix.items()}
    over = sum(counts.values()) - size
    if over != 0:
        order = sorted(counts.keys(), key=lambda k: -counts[k] if over > 0 else counts[k])
        counts[order[0]] -= over
    plan: list[str] = []
    for slot, n in counts.items():
        plan.extend([slot] * n)
    random.Random(seed).shuffle(plan)
    return plan


def _applicable_for(pack: PackDefinition, spec: EncounterSpec) -> list[DefectInjector]:
    return [cls() for cls in pack.injectors if cls().applies(spec)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--cohort",
        default=Path(__file__).resolve().parent.parent / "data" / "synthea_sample_data_csv_latest",
        type=Path,
    )
    ap.add_argument("--pack", required=True, choices=sorted(PACKS.keys()))
    ap.add_argument("--size", type=int, default=50)
    ap.add_argument(
        "--mix",
        default="clean=0.4,single=0.5,multi=0.1",
        help="comma-separated slot=proportion",
    )
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    pack = PACKS[args.pack]
    out_path = args.out or (
        Path(__file__).resolve().parent.parent / "out" / f"{pack.name}.jsonl"
    )

    mix = {k: float(v) for k, v in (kv.split("=") for kv in args.mix.split(","))}
    if abs(sum(mix.values()) - 1.0) > 0.001:
        sys.exit(f"--mix proportions must sum to 1.0; got {sum(mix.values())}")
    if len(pack.injectors) < 2 and mix.get("multi", 0) > 0:
        print(f"NOTE: pack {pack.name!r} has only {len(pack.injectors)} injector(s); "
              "multi slots will downgrade to single.")

    plan = _build_slot_plan(args.size, mix, args.seed)
    print(f"slot plan: {Counter(plan)}")

    cohort = SyntheaCohort(args.cohort)
    taxonomy = load_taxonomy()
    rng = random.Random(args.seed)

    pinned_base = {
        "generator_version": "lithrim-bench/0.1.0",
        "pack": pack.name,
        "agent_type": pack.agent_type,
        "taxonomy_snapshot": "taxonomy/taxonomy_snapshot.json",
        "seed": args.seed,
        "mix": args.mix,
        "deterministic_synthesis": True,
    }

    rows: list[dict] = []
    matrix: list[tuple[str, str, str, list[str]]] = []
    skipped: list[str] = []

    spec_iter = _walk_specs(cohort, pack.requires_active_medication)
    for slot in plan:
        spec = next(spec_iter, None)
        while spec is not None:
            applicable = _applicable_for(pack, spec)
            if slot == "clean":
                break
            if slot == "single" and applicable:
                break
            if slot == "multi" and len(applicable) >= 2:
                break
            if slot == "multi" and len(pack.injectors) < 2:
                if applicable:
                    break
            spec = next(spec_iter, None)
        if spec is None:
            skipped.append(slot)
            continue

        applicable = _applicable_for(pack, spec)
        transcript = pack.transcript_fn(spec)
        artifacts = pack.artifact_fn(spec)
        if isinstance(artifacts, dict):
            artifacts = [artifacts]
        pinned = {**pinned_base, "synthea_cohort_sha256": spec.provenance.cohort_sha256}

        recipes = []
        if slot == "single" or (slot == "multi" and len(applicable) < 2):
            inj = rng.choice(applicable)
            result = inj.inject(spec, transcript, artifacts)
            transcript = result.transcript
            artifacts = result.artifacts
            recipes = [result.recipe]
            pinned["injectors"] = [type(inj).__name__]
        elif slot == "multi":
            chosen = rng.sample(applicable, 2)
            for inj in chosen:
                result = inj.inject(spec, transcript, artifacts)
                transcript = result.transcript
                artifacts = result.artifacts
                recipes.append(result.recipe)
            pinned["injectors"] = [type(inj).__name__ for inj in chosen]

        row = package_case(
            spec=spec,
            pack=pack.name,
            agent_type=pack.agent_type,
            transcript=transcript,
            artifacts=artifacts,
            recipes=recipes,
            taxonomy=taxonomy,
            pinned=pinned,
        )
        rows.append(row)
        matrix.append((row["case_id"], slot, row["expected_compliance_verdict"], row["expected_safety_flags"]))

    write_jsonl(rows, out_path)

    matrix_path = out_path.with_suffix(".design_matrix.md")
    lines = [
        f"# {pack.name} design matrix",
        "",
        f"- agent_type: {pack.agent_type}",
        f"- seed: {args.seed}",
        f"- requested: {args.size}",
        f"- produced: {len(rows)}",
        f"- mix produced: {dict(Counter(s for _, s, _, _ in matrix))}",
        f"- skipped (cohort exhausted): {Counter(skipped)}" if skipped else "- skipped: none",
        "",
        "| case_id | slot | verdict | flags |",
        "|---|---|---|---|",
    ]
    for case_id, slot, verdict, flags in matrix:
        lines.append(f"| `{case_id}` | {slot} | {verdict} | {', '.join(flags) or '(none)'} |")
    matrix_path.write_text("\n".join(lines) + "\n")

    print(f"wrote {len(rows)} rows -> {out_path}")
    print(f"wrote design matrix -> {matrix_path}")
    if skipped:
        print(f"WARN: {len(skipped)} cases skipped: {Counter(skipped)}")


if __name__ == "__main__":
    main()
