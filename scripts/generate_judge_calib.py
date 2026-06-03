"""Build the by-construction judge-calibration corpus (WS-6c-DSPy-3a).

The DSPy-judge optimizer (WS-6c-DSPy-3b) is data-blocked: the existing corpus
has <=1 council-judge positive per judge and ZERO for `policy`. This builder
authors a per-judge recipe=label trainset — labels true by construction (the
CLAUDE.md core invariant) — covering policy / risk / faithfulness positives,
clean negatives, and a cross-owner multi-defect case.

It REUSES the existing primitives (the injectors, the per-pack synthesizers via
lithrim_bench.packs.PACKS, and packager.package_case). It does NOT run an
optimizer and makes NO live calls — $0 / offline.

Determinism: the cohort walk is deterministic, rows are emitted sorted by
case_id, and packager's wall-clock `generated_at` is overwritten with a fixed
timestamp so a regenerated corpus is byte-identical (the offline-determinism
invariant). Verify with:

    python scripts/generate_judge_calib.py --out /tmp/a.jsonl
    python scripts/generate_judge_calib.py --out /tmp/b.jsonl
    diff /tmp/a.jsonl /tmp/b.jsonl   # -> empty

Usage:
    python scripts/generate_judge_calib.py [--out examples/judge_calib_v1.jsonl]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lithrim_bench.encounter_spec import EncounterSpec
from lithrim_bench.injectors import (
    DefectInjector,
    FabricatedConsentInjector,
    FabricatedHistoryInjector,
    MissedEscalationInjector,
    MissingAllergyInjector,
    PhiDisclosurePreVerificationInjector,
    ValueMismatchInjector,
    WrongDosageInjector,
)
from lithrim_bench.packager import package_case, write_jsonl
from lithrim_bench.packs import PACKS, PackDefinition
from lithrim_bench.synthea_loader import SyntheaCohort
from lithrim_bench.taxonomy import Taxonomy, load_taxonomy

# A frozen timestamp so the corpus is byte-deterministic. packager.package_case
# stamps datetime.now(); we overwrite it. The value is the cycle date — a
# constant, not a wall-clock read.
FROZEN_TIMESTAMP = "2026-06-03T00:00:00+00:00"

PINNED_BASE = {
    "generator_version": "lithrim-bench/0.1.0",
    "builder": "scripts/generate_judge_calib.py",
    "taxonomy_snapshot": "taxonomy/taxonomy_snapshot.json",
    "deterministic_synthesis": True,
}

# (lens, pack name, injector factory, target positive count). Order is fixed so
# the walk is deterministic. Counts are targets; the builder logs any shortfall
# rather than padding.
POSITIVE_TARGETS: list[tuple[str, str, type[DefectInjector], int]] = [
    ("policy", "scheduling_v1", FabricatedConsentInjector, 6),
    ("policy", "scheduling_v1", PhiDisclosurePreVerificationInjector, 6),
    ("risk", "scribe_v1", WrongDosageInjector, 6),
    ("risk", "triage_v1", MissedEscalationInjector, 6),
    ("faithfulness", "scribe_v1", MissingAllergyInjector, 6),
    ("faithfulness", "scribe_v1", ValueMismatchInjector, 6),
    ("faithfulness", "scribe_v1", FabricatedHistoryInjector, 6),
]

# Clean negatives per pack (to measure false-positive over-firing).
CLEAN_TARGETS: list[tuple[str, int]] = [
    ("scribe_v1", 4),
    ("scheduling_v1", 2),
    ("triage_v1", 2),
]

# Cross-owner multi-defect (the co-raise lens fixture, D4): WRONG_DOSAGE (risk)
# + MISSING_ALLERGY (faithfulness) on one scribe encounter.
MULTI_TARGET = ("scribe_v1", [WrongDosageInjector, MissingAllergyInjector], 2)


def _walk_specs(cohort: SyntheaCohort, requires_med: bool) -> Iterator[EncounterSpec]:
    for pid in cohort.patient_ids():
        spec = (
            cohort.first_encounter_with_active_medication(pid)
            if requires_med
            else cohort.first_encounter(pid)
        )
        if spec is not None:
            yield spec


def _artifacts_for(pack: PackDefinition, spec: EncounterSpec) -> list[dict[str, Any]]:
    artifacts = pack.artifact_fn(spec)
    return [artifacts] if isinstance(artifacts, dict) else artifacts


def _package(
    *,
    spec: EncounterSpec,
    pack: PackDefinition,
    transcript: str,
    artifacts: list[dict[str, Any]],
    recipes: list[Any],
    taxonomy: Taxonomy,
    extra_pinned: dict[str, Any],
) -> dict[str, Any]:
    pinned = {
        **PINNED_BASE,
        "synthea_cohort_sha256": spec.provenance.cohort_sha256,
        **extra_pinned,
    }
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
    row["generated_at"] = FROZEN_TIMESTAMP
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--cohort",
        default=Path(__file__).resolve().parent.parent / "data" / "synthea_sample_data_csv_latest",
        type=Path,
    )
    ap.add_argument(
        "--out",
        default=Path(__file__).resolve().parent.parent / "examples" / "judge_calib_v1.jsonl",
        type=Path,
    )
    args = ap.parse_args()

    cohort = SyntheaCohort(args.cohort)
    taxonomy = load_taxonomy()

    rows_by_id: dict[str, dict[str, Any]] = {}
    coverage: Counter[str] = Counter()
    shortfalls: list[str] = []

    def _add(row: dict[str, Any]) -> bool:
        if row["case_id"] in rows_by_id:
            return False
        rows_by_id[row["case_id"]] = row
        return True

    # ── positives ────────────────────────────────────────────────────────────
    for lens, pack_name, inj_cls, count in POSITIVE_TARGETS:
        pack = PACKS[pack_name]
        inj = inj_cls()
        produced = 0
        for spec in _walk_specs(cohort, pack.requires_active_medication):
            if produced >= count:
                break
            if not inj.applies(spec):
                continue
            transcript = pack.transcript_fn(spec)
            artifacts = _artifacts_for(pack, spec)
            try:
                result = inj.inject(spec, transcript, artifacts)
            except ValueError:
                continue
            row = _package(
                spec=spec,
                pack=pack,
                transcript=result.transcript,
                artifacts=result.artifacts,
                recipes=[result.recipe],
                taxonomy=taxonomy,
                extra_pinned={"lens": lens, "injectors": [inj_cls.__name__]},
            )
            if _add(row):
                produced += 1
                coverage[result.recipe.safety_flag] += 1
        if produced < count:
            shortfalls.append(f"{inj_cls.__name__}: {produced}/{count}")

    # ── clean negatives ───────────────────────────────────────────────────────
    for pack_name, count in CLEAN_TARGETS:
        pack = PACKS[pack_name]
        produced = 0
        for spec in _walk_specs(cohort, pack.requires_active_medication):
            if produced >= count:
                break
            transcript = pack.transcript_fn(spec)
            artifacts = _artifacts_for(pack, spec)
            row = _package(
                spec=spec,
                pack=pack,
                transcript=transcript,
                artifacts=artifacts,
                recipes=[],
                taxonomy=taxonomy,
                extra_pinned={"lens": "clean"},
            )
            if _add(row):
                produced += 1
                coverage["(clean)"] += 1
        if produced < count:
            shortfalls.append(f"clean {pack_name}: {produced}/{count}")

    # ── cross-owner multi-defect (co-raise fixture) ───────────────────────────
    pack_name, inj_classes, count = MULTI_TARGET
    pack = PACKS[pack_name]
    injectors = [c() for c in inj_classes]
    produced = 0
    for spec in _walk_specs(cohort, pack.requires_active_medication):
        if produced >= count:
            break
        if not all(i.applies(spec) for i in injectors):
            continue
        transcript = pack.transcript_fn(spec)
        artifacts = _artifacts_for(pack, spec)
        recipes = []
        try:
            for inj in injectors:
                result = inj.inject(spec, transcript, artifacts)
                transcript = result.transcript
                artifacts = result.artifacts
                recipes.append(result.recipe)
        except ValueError:
            continue
        row = _package(
            spec=spec,
            pack=pack,
            transcript=transcript,
            artifacts=artifacts,
            recipes=recipes,
            taxonomy=taxonomy,
            extra_pinned={"lens": "multi", "injectors": [c.__name__ for c in inj_classes]},
        )
        if _add(row):
            produced += 1
            coverage["(multi)"] += 1
    if produced < count:
        shortfalls.append(f"multi {pack_name}: {produced}/{count}")

    rows = [rows_by_id[k] for k in sorted(rows_by_id)]
    write_jsonl(rows, args.out)

    print(f"wrote {len(rows)} cases -> {args.out}")
    print("coverage (code x count):")
    for code, n in sorted(coverage.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {code:40} x{n}")
    split_counts = Counter(r["split"] for r in rows)
    print(f"split (3b train/held-out): {dict(split_counts)}")
    if shortfalls:
        print(f"SHORTFALLS (cohort-capped): {shortfalls}")


if __name__ == "__main__":
    main()
