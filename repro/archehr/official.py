"""Score-only process: the prediction/feedback path never imports this module or a key."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from .run import digest, inspect_submission, read_json, validate_inputs, write_json

UPSTREAM_REVISION = "344b67e2f9c5d3c9510a77eb8bfd00b89f505b5b"
SCORER_SHA256 = "947357e3f22868d5869d90632fcb9e7203d2688118f35d4e3e2941271752d250"
SCORER_URL = (
    "https://raw.githubusercontent.com/soni-sarvesh/archehr-qa-2026/"
    + UPSTREAM_REVISION
    + "/evaluation/scoring_subtask_4.py"
)


def check_key(inputs: dict, key) -> None:
    if not isinstance(key, list) or not key:
        raise ValueError("key must be a nonempty list")
    expected = {c["case_id"]: c for c in inputs["cases"]}
    seen = set()
    for case in key:
        cid = case["case_id"]
        if cid in seen:
            raise ValueError("duplicate case in key")
        seen.add(cid)
        if cid not in expected:
            raise ValueError("key case coverage differs from inputs")
        notes = {n["id"] for n in expected[cid]["note_sentences"]}
        answers = {a["id"] for a in expected[cid]["answer_sentences"]}
        answer_ids = [a["id"] for a in case["clinician_answer_sentences"]]
        source_ids = [n["sentence_id"] for n in case["answers"]]
        if len(answer_ids) != len(set(answer_ids)) or len(source_ids) != len(set(source_ids)):
            raise ValueError("duplicate sentence IDs in key")
        if set(answer_ids) != answers or set(source_ids) != notes:
            raise ValueError("key sentence IDs differ from inputs")
        for answer in case["clinician_answer_sentences"]:
            citations = answer["citations"]
            if not isinstance(citations, list) or any(c not in notes for c in citations):
                raise ValueError("key contains invalid citations")
    if seen != set(expected):
        raise ValueError("key case coverage differs from inputs")


def score_official(
    *,
    scorer_path: Path,
    inputs_path: Path,
    submission_path: Path,
    key_path: Path,
    output_dir: Path,
) -> dict:
    script = scorer_path.read_bytes()
    if hashlib.sha256(script).hexdigest() != SCORER_SHA256:
        raise ValueError("scorer hash mismatch; only the pinned upstream script is allowed")
    inputs = read_json(inputs_path)
    validate_inputs(inputs)
    submission = read_json(submission_path)
    issues = inspect_submission(inputs, submission)
    if issues:
        raise ValueError(f"invalid submission: {issues}")
    key = read_json(key_path)
    check_key(inputs, key)
    output_dir.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="archehr-score-") as directory:
        scratch = Path(directory)
        scorer_copy = scratch / "scoring_subtask_4.py"
        scorer_copy.write_bytes(script)
        write_json(scratch / "submission.json", submission)
        write_json(scratch / "key.json", key)
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                str(scorer_copy),
                "--submission_path",
                str(scratch / "submission.json"),
                "--key_path",
                str(scratch / "key.json"),
                "--out_file_path",
                str(scratch / "scores.json"),
            ],
            cwd=scratch,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode:
            write_json(
                output_dir / "failure.json",
                {
                    "returncode": result.returncode,
                    "scorer_sha256": SCORER_SHA256,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
            )
            raise ValueError("official scoring failed; see local failure.json (may contain IDs)")
        scores = read_json(scratch / "scores.json")
    report = {
        "score_kind": "synthetic_plumbing_not_benchmark"
        if inputs["dataset"]["split"] == "smoke"
        else "local_official_scorer_not_leaderboard",
        "dataset": inputs["dataset"],
        "case_count": len(inputs["cases"]),
        "case_ids": [c["case_id"] for c in inputs["cases"]],
        "inputs_sha256": digest(inputs),
        "submission_sha256": digest(submission),
        "key_sha256": digest(key),
        "scorer_sha256": SCORER_SHA256,
        "upstream_revision": UPSTREAM_REVISION,
        "scorer_url": SCORER_URL,
        "scores": scores,
        "leaderboard_submission": False,
        "limitation": "IDs and hashes pin this local run; dataset authenticity and prior exposure require an access/provenance audit.",
    }
    write_json(output_dir / "scores.json", scores)
    write_json(output_dir / "report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("scorer", "inputs", "submission", "key", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        report = score_official(
            scorer_path=args.scorer,
            inputs_path=args.inputs,
            submission_path=args.submission,
            key_path=args.key,
            output_dir=args.out,
        )
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(
        json.dumps(
            {
                "score_kind": report["score_kind"],
                "scores": report["scores"],
                "output": str(args.out.resolve()),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
