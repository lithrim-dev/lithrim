#!/usr/bin/env python
"""The RAGTruth dataset adapter: the two upstream JSONL files -> ``_core``-shaped eval cases.

RAGTruth (Wu et al., arXiv:2401.00396; github.com/ParticleMedia/RAGTruth; MIT): 17,790 LLM
responses over 2,965 sources (news summarization, MS MARCO QA, Yelp data-to-text), with
HUMAN span-level hallucination labels. Every response links to its source, so the reviewer's
grounding checks have something to check against.

This file is the dataset-specific half of the loop, kept OUT of the engine. ``lithrim load``
calls its adapter contract (``download``, ``slice_cases``, ``calibration_corpus``); the label
map is the ``kind: importer`` manifest ``packs/_core/importers/ragtruth.json``, so an unmapped
label type fails admissibility (LookupError), never a silent drop.

Labels are HUMAN-ANNOTATED (``ground_truth_basis: human_annotated``), not by construction:
``expected_safety_flags`` maps RAGTruth label types onto the ``_core`` taxonomy
(Conflict -> SOURCE_CONTRADICTION, Baseless Info -> UNSUPPORTED_ASSERTION) and the original
spans ride along under ``ragtruth.labels`` as the evidence for that mapping (the manifest's
``gold_spans_path``).

Run directly, it also builds the tracked queue sample (``samples/ragtruth/cases.jsonl``): five
cases chosen by a STATED, deterministic rule, not by hand:

  eligible = test split, quality == good, source text < 3500 chars, no medical vocabulary and
             none of the CE data-surface sweep needles (the tree keeps that data on its
             sanctioned surfaces only; see _SWEEP_NEEDLES)
  R1  data-to-text, the value_grounding floor VIOLATES and a human span covers a missing value
  R2  data-to-text, the floor PASSES with >= 3 values checked, no human labels
  R3  news summary, human-labeled (baseless info), the floor has no values to check
  R4  news summary, the floor finds a missing value AND a human span covers it (a named lead)
  R5  QA, the floor PASSES with >= 2 values checked, no human labels
  within each rule: shortest source first, then lowest response id

Usage:
    python examples/ragtruth/adapter.py --data-dir /path/with/response.jsonl+source_info.jsonl
    python examples/ragtruth/adapter.py --download   # fetch the two files into out/ragtruth/ first
    python examples/ragtruth/adapter.py --slice 15 --out out/ragtruth/slice.jsonl   # a grading slice
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.harness.plugins import importer_vocabulary  # noqa: E402
from lithrim_bench.verification import (  # noqa: E402
    STRUCTURAL_CONFORMANCE,
    TOOL_VALUE_GROUNDING,
    Claim,
    ValueGroundingTool,
    VerificationSpec,
)

RAW_BASE = "https://raw.githubusercontent.com/ParticleMedia/RAGTruth/main/dataset/"
FILES = ("response.jsonl", "source_info.jsonl")
OUT = REPO_ROOT / "samples/ragtruth/cases.jsonl"
MAX_SOURCE_CHARS = 3500
_MEDICAL = re.compile(
    r"\b(patient|diagnos|hospital|clinic|dose|mg\b|physician|nurse|symptom|disease|cancer|medic)",
    re.I,
)
# The CE data-surface sweep (tests/test_pack_dist.py::_NEEDLES) rejects any of these substrings in
# a tracked file under examples/. A mirror, guarded against drift by tests/test_queue_demo.py, so
# the sample stays needle-free BY CONSTRUCTION (note "scribe" also matches "describe").
_SWEEP_NEEDLES = (
    "patient", "medication", "dosage", "allerg", "clinical", "soap", "scribe", "snomed",
    "icd10", "icd-10", "escalat", "hipaa", "diagnos", "prescri",
)


def _needle_free(*texts: str) -> bool:
    low = " ".join(texts).lower()
    return not any(n in low for n in _SWEEP_NEEDLES)


_VOCAB = importer_vocabulary("ragtruth", pack="_core")
_SPEC = VerificationSpec(
    tool=TOOL_VALUE_GROUNDING,
    applies_to_flags=("SOURCE_CONTRADICTION",),
    locus="",
    reference={"rating_units": ["star"]},
    version="value-grounding/3",
)


def _source_text(src: dict) -> str:
    info = src["source_info"]
    return info if isinstance(info, str) else json.dumps(info, ensure_ascii=False)


def _source_kind(src: dict) -> str:
    return "record" if src["task_type"] == "Data2txt" else "prose"


def _case(resp: dict, src: dict) -> dict:
    labels = resp.get("labels") or []
    flags = sorted({_VOCAB.code_for(lab["label_type"]) for lab in labels})
    return {
        "case_id": f"ragtruth_{resp['id']}",
        "pack": "_core",
        "ground_truth_basis": "human_annotated",
        "annotation_source": "RAGTruth (ParticleMedia/RAGTruth, MIT; arXiv:2401.00396)",
        "source_kind": _source_kind(src),
        "transcript": _source_text(src),
        "artifacts": [{"type": "generated_response", "content": resp["response"]}],
        "expected_compliance_verdict": "reject" if flags else "approve",
        "expected_artifact_verdict": "BLOCK" if flags else "PASS",
        "expected_safety_flags": flags,
        "clean_negative": not flags,
        "multi_defect": len(flags) > 1,
        "severity": "high" if flags else "none",
        "injection_recipes": None,
        "label_justification": (
            "human span annotation (RAGTruth); see ragtruth.labels for the annotated spans"
            if flags
            else "no human-annotated hallucination span (RAGTruth clean response)"
        ),
        "ragtruth": {
            "id": resp["id"],
            "source_id": resp["source_id"],
            "model": resp["model"],
            "task_type": src["task_type"],
            "labels": [
                {
                    **{k: lab[k] for k in ("start", "end", "text", "label_type") if k in lab},
                    "code": _VOCAB.code_for(lab["label_type"]),
                    "subtlety": str(lab.get("label_type", "")).split(" ", 1)[0] or None,
                    **{k: lab[k] for k in ("implicit_true", "due_to_null") if k in lab},
                }
                for lab in labels
            ],
            "vocabulary": _VOCAB.id,
        },
        "pinned": {"pack": "_core", "taxonomy_snapshot": "packs/_core/taxonomy_snapshot.json"},
    }


def _floor(case: dict):
    claim = Claim(
        claim_type=STRUCTURAL_CONFORMANCE,
        flag_code="SOURCE_CONTRADICTION",
        subject=case["artifacts"][0]["content"],
        locus="",
        source=case,
    )
    return ValueGroundingTool().verify(claim, _SPEC)


def _label_covers(missing: list[str], labels: list[dict]) -> bool:
    return any(any(m in lab.get("text", "") for m in missing) for lab in labels)


def select(responses: list[dict], sources: dict[str, dict]) -> list[tuple[str, dict]]:
    pool = []
    for r in responses:
        if r.get("split") != "test" or r.get("quality") != "good":
            continue
        s = sources[r["source_id"]]
        st = _source_text(s)
        if len(st) >= MAX_SOURCE_CHARS or _MEDICAL.search(st) or _MEDICAL.search(r["response"]):
            continue
        if not _needle_free(st, r["response"], json.dumps(r.get("labels") or [])):
            continue
        case = _case(r, s)
        vr = _floor(case)
        ev = vr.evidence
        pool.append((r, s, case, vr, ev))

    def pick(rule, pred):
        xs = [x for x in pool if pred(*x)]
        xs.sort(key=lambda x: (len(_source_text(x[1])), int(x[0]["id"])))
        if not xs:
            raise SystemExit(f"no candidate for {rule}")
        return rule, xs[0][2]

    return [
        pick("R1", lambda r, s, c, vr, ev: s["task_type"] == "Data2txt" and vr.conforms is False
             and _label_covers(ev.get("missing", []), r.get("labels") or [])),
        pick("R2", lambda r, s, c, vr, ev: s["task_type"] == "Data2txt" and vr.conforms is True
             and ev.get("checked", 0) >= 3 and not r.get("labels")),
        pick("R3", lambda r, s, c, vr, ev: s["task_type"] == "Summary" and r.get("labels")
             and vr.conforms is None and not ev.get("missing")
             and all(lab["label_type"].endswith("Baseless Info") for lab in r["labels"])),
        pick("R4", lambda r, s, c, vr, ev: s["task_type"] == "Summary" and vr.conforms is None
             and ev.get("missing") and _label_covers(ev["missing"], r.get("labels") or [])),
        pick("R5", lambda r, s, c, vr, ev: s["task_type"] == "QA" and vr.conforms is True
             and ev.get("checked", 0) >= 2 and not r.get("labels")),
    ]


def select_slice(
    responses: list[dict],
    sources: dict[str, dict],
    per_task: int,
    *,
    natural: bool = False,
    split: str = "test",
) -> list[tuple[str, dict]]:
    """A deterministic per-task slice for grading experiments (not the tracked sample): the
    test split, quality good, source under MAX_SOURCE_CHARS, one response per source. Per
    task: the human-labeled half first (rounded up), then the clean half, each pool filled
    lowest response id first while keeping the generating models balanced (the earliest id
    among the least-picked models wins), so a small slice still yields a precision AND a
    recall over more than one generator.

    ``natural=True`` is the paper-comparable cut: no label stratification and no source
    length cap, one model-balanced response per source at the corpus's own hallucination
    rate (the full test split is 450 sources, 150 per task)."""
    pools: dict[str, dict[bool, list[dict]]] = {}
    for r in sorted(responses, key=lambda r: int(r["id"])):
        if r.get("split") != split or r.get("quality") != "good":
            continue
        s = sources[r["source_id"]]
        if not natural and len(_source_text(s)) >= MAX_SOURCE_CHARS:
            continue
        key = True if natural else bool(r.get("labels"))
        pools.setdefault(s["task_type"], {True: [], False: []})[key].append(r)

    def fill(rows: list[dict], n: int, used_sources: set[str]) -> list[dict]:
        picked: list[dict] = []
        per_model: dict[str, int] = {}
        candidates = [r for r in rows if r["source_id"] not in used_sources]
        while len(picked) < n and candidates:
            floor_count = min(per_model.get(r["model"], 0) for r in candidates)
            r = next(c for c in candidates if per_model.get(c["model"], 0) == floor_count)
            picked.append(r)
            per_model[r["model"]] = per_model.get(r["model"], 0) + 1
            used_sources.add(r["source_id"])
            candidates = [c for c in candidates if c["source_id"] not in used_sources]
        return picked

    picked: list[tuple[str, dict]] = []
    for task in sorted(pools):
        used: set[str] = set()
        n_lab = per_task if natural else (per_task + 1) // 2
        rows = fill(pools[task][True], n_lab, used) + fill(
            pools[task][False], per_task - n_lab, used
        )
        for r in rows:
            case = _case(r, sources[r["source_id"]])
            case["split"] = "calibration" if split == "train" else "test"
            picked.append((f"slice:{task}", case))
    return picked


def interleave_tasks(cases: list[dict]) -> list[dict]:
    """Round-robin the three tasks so any prefix cap (the optimizer's ``--limit``) samples
    every task, not the first task in file order."""
    by_task: dict[str, list[dict]] = {}
    for c in cases:
        by_task.setdefault(c["ragtruth"]["task_type"], []).append(c)
    out: list[dict] = []
    for i in range(max((len(v) for v in by_task.values()), default=0)):
        for task in sorted(by_task):
            if i < len(by_task[task]):
                out.append(by_task[task][i])
    return out


def calib_row(case: dict, split: str) -> dict:
    """One optimizer corpus row (``judge_optimize.load_corpus`` shape) with the provenance the
    split-hygiene checks need: ``source_id`` (RAGTruth splits per source) and the task type."""
    return {
        "case_id": case["case_id"],
        "transcript": case["transcript"],
        "artifacts": case["artifacts"],
        "expected_safety_flags": case["expected_safety_flags"],
        "ground_truth_basis": case["ground_truth_basis"],
        "split": split,
        "ragtruth": {
            "source_id": case["ragtruth"]["source_id"],
            "task_type": case["ragtruth"]["task_type"],
            "model": case["ragtruth"]["model"],
        },
    }


def build_calib_corpus(
    responses: list[dict], sources: dict[str, dict], per_task: int, test_cases: list[dict]
) -> list[dict]:
    """The holdout-hygienic optimizer corpus, built from RAGTruth's TRAIN split alone (the same
    natural, model-balanced, one-per-source rule as the test cut): ``calibration`` rows train the
    demos and a deterministic, source-disjoint ``dev`` slice (``DEV_FRACTION`` of each task's
    sources) is what the pin gate scores on. The graded test cut is NOT in the corpus: it stays
    untouched until the after round (HOLDOUT-DEV-1; before 2026-09-10 the gate read the test
    cut). Refuses to build if any calibration source is also a test source (RAGTruth assigns its
    split per source, so this should never fire)."""
    from lithrim_bench.harness.calib_corpus import carve_dev

    calib = [c for _, c in select_slice(responses, sources, per_task, natural=True, split="train")]
    test_sources = {c["ragtruth"]["source_id"] for c in test_cases}
    shared = {c["ragtruth"]["source_id"] for c in calib} & test_sources
    if shared:
        raise SystemExit(f"calibration and test share {len(shared)} source(s): {sorted(shared)[:5]}")
    rows = [calib_row(c, "calibration") for c in calib]
    carved = carve_dev(
        rows,
        source_of=lambda r: r["ragtruth"]["source_id"],
        group_of=lambda r: r["ragtruth"]["task_type"],
    )
    by_id = {c["case_id"]: c for c in calib}
    train = interleave_tasks([by_id[r["case_id"]] for r in carved if r["split"] == "calibration"])
    dev = interleave_tasks([by_id[r["case_id"]] for r in carved if r["split"] == "dev"])
    return [calib_row(c, "calibration") for c in train] + [calib_row(c, "dev") for c in dev]


# --------------------------------------------------------------------------- #
# the adapter contract ``lithrim load`` calls (lithrim_bench/cli/adapters.py)
# --------------------------------------------------------------------------- #
def download(data_dir: Path) -> None:
    """Fetch the two upstream files into ``data_dir`` when absent (no-op when present)."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        p = data_dir / name
        if not p.exists():
            print(f"downloading {RAW_BASE + name} -> {p}", flush=True)
            urllib.request.urlretrieve(RAW_BASE + name, p)


def load_corpus(data_dir: Path) -> tuple[list[dict], dict[str, dict]]:
    data_dir = Path(data_dir)
    for name in FILES:
        if not (data_dir / name).exists():
            raise SystemExit(f"{data_dir / name} missing; download the RAGTruth dataset files first")
    responses = [json.loads(line) for line in (data_dir / "response.jsonl").open()]
    sources = {
        d["source_id"]: d
        for d in (json.loads(line) for line in (data_dir / "source_info.jsonl").open())
    }
    return responses, sources


def slice_cases(
    data_dir: Path, *, per_task: int, split: str = "test", natural: bool = True
) -> list[dict]:
    responses, sources = load_corpus(data_dir)
    out = []
    for rule, case in select_slice(responses, sources, per_task, natural=natural, split=split):
        case["ragtruth"]["selection_rule"] = rule
        out.append(case)
    return out


def calibration_corpus(data_dir: Path, *, per_task: int, test_cases: list[dict]) -> list[dict]:
    responses, sources = load_corpus(data_dir)
    return build_calib_corpus(responses, sources, per_task, test_cases)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=REPO_ROOT / "out/ragtruth")
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument(
        "--slice", type=int, default=0, metavar="N",
        help="write a per-task grading slice of N cases per task (stratified labeled/clean) "
             "instead of the five-rule tracked sample; pair with --out under out/",
    )
    ap.add_argument(
        "--split",
        choices=["test", "train"],
        default="test",
        help="with --slice: which RAGTruth split to cut (train = the calibration side; the "
        "case carries split=calibration so a gold row is never mistaken for a test row)",
    )
    ap.add_argument(
        "--natural", action="store_true",
        help="with --slice: no label stratification, no source length cap (the paper-comparable "
             "cut; --slice 150 --natural is the whole test split, one response per source)",
    )
    ap.add_argument(
        "--calib-out", type=Path, default=None,
        help="also write the optimizer corpus: RAGTruth TRAIN-split rows as `calibration` "
             "(same per-task count and rule as --slice --natural) + this slice as `test`",
    )
    args = ap.parse_args()
    if args.download:
        download(args.data_dir)
    responses, sources = load_corpus(args.data_dir)
    picked = (
        select_slice(responses, sources, args.slice, natural=args.natural, split=args.split)
        if args.slice
        else select(responses, sources)
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as fh:
        for rule, case in picked:
            case["ragtruth"]["selection_rule"] = rule
            fh.write(json.dumps(case, ensure_ascii=False) + "\n")
    for rule, case in picked:
        rt = case["ragtruth"]
        print(f"{rule} {case['case_id']:16s} {rt['task_type']:9s} {rt['model']:22s} "
              f"flags={case['expected_safety_flags']} src_chars={len(case['transcript'])}")
    print(f"wrote {args.out}")
    if args.calib_out:
        if not (args.slice and args.natural):
            sys.exit("--calib-out needs --slice N --natural (the test rows are this natural cut)")
        rows = build_calib_corpus(responses, sources, args.slice, [c for _, c in picked])
        args.calib_out.parent.mkdir(parents=True, exist_ok=True)
        with args.calib_out.open("w") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        n_cal = sum(1 for r in rows if r["split"] == "calibration")
        print(f"wrote {args.calib_out}: {n_cal} calibration + {len(rows) - n_cal} test rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
