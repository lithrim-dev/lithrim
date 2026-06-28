#!/usr/bin/env python3
"""Extract the Clinical Scribe Review golden suite into a lithrim-bench importable corpus.

Clinical Scribe Review (Dr. Rivera's physician-curated eval suite) stores each case as
human-authored markdown across THREE files that must be joined:

  1. data_assets/Case_XX*.md         -> 4 fenced blocks in fixed order:
                                          [transcript, AGENT SOAP, human reference, judge report]
                                        (headers are inconsistent/typo'd, so we parse POSITIONALLY)
  2. analytics/README.md             -> the master matrix: per-case clinician verdict +
                                          agent errors / judge fallacy / reference defects
  3. analytics/deep_dives/Case_XX*.md -> freeform rationale (path referenced, not parsed in v1)

Output: one JSON object per case (NDJSON) shaped as a second-class "physician_asserted"
imported row (cf. lithrim_bench/importers/backend_demo.py). The clinician verdict is the
GOLD label; the human reference note is demoted to a non-grading auditable input; the
proposed safety-flag codes are derived from the matrix and WILL quarantine until
registered in the taxonomy snapshot (WS-2).

Usage:
    python scripts/extract_clinical_scribe.py \
        --src /path/to/Clinical Scribe Review-...-Evals-Suite \
        --out out/clinical_scribe_v1.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# --- constants describing the source pipeline (same for every case) ---------------
PIPELINE_UNDER_TEST = {
    "agent": "two-skill clinical scribe",
    "skill_1_model": "llama-3.3-70b-versatile (Groq)",
    "skill_2_model": "llama-3.3-70b-versatile (Groq)",
    "judge_model": "gemini-2.5-flash (single judge)",
}
SOURCE_DATASET = {
    "dataset": "MTS_Dialogue-Clinical_Note",
    "huggingface_id": "har1/MTS_Dialogue-Clinical_Note",
    "mts_sample_index": None,  # not recorded per-case in the repo; recover from Rivera
    "license": "open-access (verify redistribution terms before publishing)",
}
SPECIALTY_KEYWORDS = {
    "neurology": "neurology", "hiv": "neurology",
    "lumbar": "neurology", "puncture": "neurology",
    "kidney": "nephrology",
    "blood_cancer": "oncology", "cancer": "oncology", "polycythemia": "oncology",
    "psychology": "psychiatry", "psych": "psychiatry",
    "diabetes": "endocrinology",
    "pediatrics": "pediatrics", "seizure": "pediatrics",
    "splinter": "emergency", "foreign": "emergency", "injury": "emergency",
    "negative": "general",
}

FENCE_RE = re.compile(r"```[a-zA-Z0-9_-]*\n(.*?)```", re.DOTALL)
SCORE_RE = re.compile(r"(FAITHFULNESS|COMPLETENESS|SAFETY)\s*:\s*(\d)\s*/\s*5", re.IGNORECASE)
SOAP_RE = re.compile(
    r"S\s*\(Subjective\)\s*:(?P<s>.*?)"
    r"O\s*\(Objective\)\s*:(?P<o>.*?)"
    r"A\s*\(Assessment\)\s*:(?P<a>.*?)"
    r"P\s*\(Plan\)\s*:(?P<p>.*)",
    re.DOTALL | re.IGNORECASE,
)
BOLD_PAIR_RE = re.compile(r"\*\*(?P<tag>[^*:]+?):\*\*\s*(?P<detail>.*?)(?=\*\*[^*:]+?:\*\*|$)", re.DOTALL)


def slug(text: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^A-Z0-9]+", "_", text.strip().upper())).strip("_")


def case_number(name: str) -> int:
    m = re.search(r"Case[_\s-]?0*(\d+)", name)
    return int(m.group(1)) if m else 0


def specialty_for(name: str) -> str:
    low = name.lower()
    for kw, spec in SPECIALTY_KEYWORDS.items():
        if kw in low:
            return spec
    return "general"


def parse_soap(block: str) -> dict:
    m = SOAP_RE.search(block)
    if not m:
        return {"raw": block.strip()}
    return {
        "subjective": m.group("s").strip(),
        "objective": m.group("o").strip(),
        "assessment": m.group("a").strip(),
        "plan": m.group("p").strip(),
    }


def parse_judge(block: str) -> dict:
    scores = {k.lower(): int(v) for k, v in SCORE_RE.findall(block)}
    overall = ""
    m = re.search(r"OVERALL\s*:\s*(.*)", block, re.DOTALL | re.IGNORECASE)
    if m:
        overall = re.sub(r"\s+", " ", m.group(1)).strip().rstrip("\"")
    return {
        "judge_model": "gemini-2.5-flash",
        "scores": {**scores, "scale": "1-5"},
        "overall": overall,
        "raw": block.strip(),
    }


def parse_cell_tags(cell: str) -> list[dict]:
    """A matrix cell like '**Clinical Omission:** Omitted X.<br>**Intent Erasure:** ...'
    -> [{tag: CLINICAL_OMISSION, label: 'Clinical Omission', detail: 'Omitted X.'}, ...]."""
    cell = cell.replace("<br>", " ").strip()
    if not cell or cell.lower() == "none":
        return []
    out = []
    for m in BOLD_PAIR_RE.finditer(cell):
        label = re.sub(r"\s+", " ", m.group("tag")).strip()
        detail = re.sub(r"\s+", " ", m.group("detail")).strip()
        out.append({"tag": slug(label), "label": label, "detail": detail})
    if not out:  # no bold lead-ins; keep the prose so nothing is lost
        out.append({"tag": None, "label": None, "detail": cell})
    return out


def parse_matrix(readme_text: str) -> dict[int, dict]:
    """Parse the master-matrix table rows keyed by case number."""
    rows: dict[int, dict] = {}
    for line in readme_text.splitlines():
        if not line.lstrip().startswith("|") or "data_assets/Case_" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        topic_cell, scores_cell, verdict_cell, agent_cell, judge_cell, ref_cell = cells[:6]
        num_m = re.search(r"Case_0*(\d+)", topic_cell)
        if not num_m:
            continue
        num = int(num_m.group(1))
        topic = re.sub(r"\[(.*?)\].*", r"\1", topic_cell).strip()
        topic = re.sub(r"^\d+\.\s*", "", topic)
        # Groups 2-3 wrap the verdict as '**Agent:**<br>Failed' — flatten <br>/* so the
        # label and the Failed/Passed token sit adjacent before matching.
        flat_verdict = re.sub(r"(<br>|\*)+", " ", verdict_cell)
        av = re.search(r"Agent:\s*(Failed|Passed)", flat_verdict, re.IGNORECASE)
        jv = re.search(r"Judge:\s*(Failed|Passed)", flat_verdict, re.IGNORECASE)
        scores = {k.lower(): int(v) for k, v in re.findall(r"(Faith|Comp|Safety)\w*:\s*(\d)/5", scores_cell)}
        rows[num] = {
            "topic": topic,
            "matrix_scores": scores,
            "agent_verdict": (av.group(1).upper() if av else None),
            "judge_verdict": (jv.group(1).upper() if jv else None),
            "agent_errors": parse_cell_tags(agent_cell),
            "judge_fallacy": parse_cell_tags(judge_cell),
            "reference_defects": parse_cell_tags(ref_cell),
        }
    return rows


def build_row(case_path: Path, matrix: dict, deep_dive_rel: str | None) -> dict:
    text = case_path.read_text(encoding="utf-8")
    blocks = FENCE_RE.findall(text)
    if len(blocks) != 4:
        raise ValueError(f"{case_path.name}: expected 4 fenced blocks, found {len(blocks)}")
    transcript, soap_block, reference_block, judge_block = (b.strip() for b in blocks)

    num = case_number(case_path.name)
    meta = matrix.get(num, {})
    topic = meta.get("topic") or case_path.stem
    case_id = f"clinical_scribe_{num:02d}_" + slug(topic).lower()

    agent_verdict = meta.get("agent_verdict")
    expected_verdict = {"FAILED": "reject", "PASSED": "approve"}.get(agent_verdict or "", "needs_review")
    expected_artifact = {"reject": "BLOCK", "approve": "PASS", "needs_review": "WARN"}[expected_verdict]
    proposed_flags = sorted({e["tag"] for e in meta.get("agent_errors", []) if e.get("tag")})

    return {
        "case_id": case_id,
        "suite": "Clinical Scribe Review",
        "pack": "clinical_scribe_v1",
        "agent_type": "scribe",
        "specialty": specialty_for(case_path.name),
        "topic": topic,
        "ground_truth_basis": "physician_asserted",
        "synthetic": False,
        # --- lithrim-bench case-reader contract (TOP-LEVEL): what /v1/case + the grade
        #     path read. Mirrors importers/backend_demo.py. The rich blocks below
        #     (clinician_meta_evaluation, prior_judge_report, reference_note) are extra. ---
        "expected_compliance_verdict": expected_verdict,
        "expected_artifact_verdict": expected_artifact,
        "expected_safety_flags": proposed_flags,
        "injection_recipe": None,
        "clean_negative": (expected_verdict == "approve"),
        "source_provenance": {
            **SOURCE_DATASET,
            "clinical_scribe_case_file": f"data_assets/{case_path.name}",
            "clinical_scribe_deep_dive": deep_dive_rel,
        },
        "pipeline_under_test": PIPELINE_UNDER_TEST,
        "patient_profile": {"allergies": [], "_note": "transcript is the source of truth; enrich in authoring loop"},
        "transcript": transcript,
        "artifacts": [
            {
                "artifact_id": "soap_final",
                "type": "soap_note",
                "produced_by": "skill_2",
                "is_grading_target": True,
                # Native scribe-artifact contract (cf. healthcare/generators/scribe_artifact.py):
                # content is a JSON STRING of a FHIR DocumentReference whose text/plain attachment
                # data IS the SOAP body. _artifact_note decodes it for display; the council grades
                # the same string. The SOAP is embedded VERBATIM from the Clinical Scribe Review case file.
                "content": json.dumps(
                    {
                        "resourceType": "DocumentReference",
                        "status": "current",
                        "type": {"text": "Clinical SOAP note (ambient scribe)"},
                        "content": [
                            {"attachment": {"contentType": "text/plain", "data": soap_block}}
                        ],
                    }
                ),
                "soap_structured": parse_soap(soap_block),
            }
        ],
        "skill_1_extraction": {
            "available": False,
            "note": "Not in repo markdown — only in the Phoenix trace. Needed as a 2nd artifact to RUN the inter-stage (Silent Drop) check.",
        },
        "reference_note": {
            "is_grading_target": False,
            "role": "auditable input (potentially defective) — NOT ground truth; Lithrim grades against the transcript",
            "content": reference_block,
            "asserted_defects": [d["label"] for d in meta.get("reference_defects", []) if d.get("label")],
        },
        "prior_judge_report": {
            **parse_judge(judge_block),
            "judge_meta_verdict": meta.get("judge_verdict"),  # Rivera's verdict ON the judge (FAILED = judge erred)
        },
        "clinician_meta_evaluation": {
            "calibrator": "Dr. Rivera",
            "agent_verdict": agent_verdict,
            "judge_verdict": meta.get("judge_verdict"),
            "agent_errors": meta.get("agent_errors", []),
            "judge_fallacy": meta.get("judge_fallacy", []),
            "reference_defects": meta.get("reference_defects", []),
        },
        "expected": {
            "ground_truth_source": "clinician_meta_evaluation (physician-asserted gold)",
            "expected_compliance_verdict": expected_verdict,
            "expected_artifact_verdict": expected_artifact,
            "proposed_safety_flags": proposed_flags,
            "taxonomy_note": "Proposed codes are derived from the matrix and are NOT in the frozen snapshot — they QUARANTINE until registered (WS-2). reject vs needs_review is a Calibrator calibration choice.",
        },
        "label_justification": "; ".join(
            f"{e['label']}: {e['detail']}" for e in meta.get("agent_errors", []) if e.get("label")
        ) or "See clinician_meta_evaluation.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="Path to the Clinical Scribe Review repo root")
    ap.add_argument("--out", default="out/clinical_scribe_v1.jsonl", help="Output NDJSON path")
    args = ap.parse_args()

    src = Path(args.src).expanduser().resolve()
    data_dir = src / "data_assets"
    readme = src / "analytics" / "README.md"
    deep_dir = src / "analytics" / "deep_dives"
    if not data_dir.is_dir() or not readme.is_file():
        raise SystemExit(f"Not a Clinical Scribe Review repo (missing data_assets/ or analytics/README.md): {src}")

    matrix = parse_matrix(readme.read_text(encoding="utf-8"))
    deep_files = {case_number(p.name): p for p in deep_dir.glob("*.md")} if deep_dir.is_dir() else {}

    case_files = sorted(data_dir.glob("Case_*.md"), key=lambda p: case_number(p.name))
    rows, errors = [], []
    for cf in case_files:
        try:
            num = case_number(cf.name)
            dd = deep_files.get(num)
            dd_rel = f"analytics/deep_dives/{dd.name}" if dd else None
            rows.append(build_row(cf, matrix, dd_rel))
        except Exception as e:  # noqa: BLE001 — collect and report, don't abort the batch
            errors.append(f"{cf.name}: {e}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    # --- summary ---
    print(f"matrix rows parsed: {len(matrix)}   cases written: {len(rows)} -> {out_path}")
    print(f"{'case_id':<46} {'verdict':<8} {'soap':<5} {'F/C/S':<8} flags")
    for r in rows:
        sc = r["prior_judge_report"]["scores"]
        fcs = f"{sc.get('faithfulness','-')}/{sc.get('completeness','-')}/{sc.get('safety','-')}"
        soap_ok = "S/O/A/P" if "subjective" in r["artifacts"][0].get("soap_structured", {}) else "raw"
        print(f"{r['case_id']:<46} {r['expected']['expected_compliance_verdict']:<8} "
              f"{soap_ok:<5} {fcs:<8} {','.join(r['expected']['proposed_safety_flags']) or '-'}")
    if errors:
        print("\nERRORS:")
        for e in errors:
            print(" -", e)


if __name__ == "__main__":
    main()
