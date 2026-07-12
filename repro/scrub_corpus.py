"""SCRUB-1: apply the preregistered F10 corpus correction (OSF 10.17605/OSF.IO/2ZU4H).

Pure-deletion scrub of the 44 MTS notes driven entirely by the committed
``corpus_v2/scrub_map.json``: per twin-pair, whole-line removals and sentence-level
removals within mixed lines. The map's lines come from the clean-generalization twin;
the twin bodies are identical except the PMH concept line, so each removal must match
in BOTH twins or the run aborts. Label surfaces (PMH block, twin-diff lines) are
guarded here in addition to the acceptance tests (tests/test_scrub_corpus.py).

Writes the three ``*_v2`` corpus files plus ``SCRUB_DIFF.md`` (the per-case v1->v2
unified diff deposited with Zenodo v2). Deterministic: same inputs, same bytes.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

REPRO = Path(__file__).resolve().parent
V1 = REPRO / "corpus"
V2_DEFAULT = REPRO / "corpus_v2"
MAP_PATH = REPRO / "corpus_v2" / "scrub_map.json"
FILES = [
    "clean_generalization_negatives.jsonl",
    "upcoded_positives.jsonl",
    "cv_bidirectional_44_bundle.jsonl",
]
PRE_REG = "10.17605/OSF.IO/2ZU4H"

_SECTION_PREFIX = re.compile(r"^(\s*[A-Za-z][A-Za-z0-9 /()]*:\s*)")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?]) +")
_LABEL_LINE = re.compile(r"^\s*-\s+\S|^(PMH|PAST MEDICAL HISTORY)\b")


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _pair_stem(case_id: str) -> str:
    return re.sub(r"_(clean_generalization|upcode)_", "_PAIR_", case_id)


def _get_note(row: dict) -> str:
    doc = json.loads(row["artifacts"][0]["content"])
    return doc["content"][0]["attachment"]["data"]


def _set_note(row: dict, text: str) -> None:
    doc = json.loads(row["artifacts"][0]["content"])
    doc["content"][0]["attachment"]["data"] = text
    row["artifacts"][0]["content"] = json.dumps(doc)


def _remove_sentences(line: str, sentences: list[str], case_id: str) -> str:
    prefix_match = _SECTION_PREFIX.match(line)
    prefix = prefix_match.group(1) if prefix_match else ""
    parts = [s for s in _SENTENCE_SPLIT.split(line[len(prefix) :]) if s]
    kept = list(parts)
    for target in sentences:
        if target not in kept:
            raise SystemExit(
                f"{case_id}: sentence not found in line\n  line: {line!r}\n  sentence: {target!r}"
            )
        kept.remove(target)
    if not kept:
        raise SystemExit(
            f"{case_id}: sentence removal emptied the line — use a whole-line removal\n"
            f"  line: {line!r}"
        )
    return prefix + " ".join(kept)


def _scrub_note(text: str, removals: list[dict], case_id: str) -> str:
    lines = text.split("\n")
    for entry in removals:
        target, sentences = entry["line"], entry.get("sentences")
        if _LABEL_LINE.match(target):
            raise SystemExit(f"{case_id}: map targets a label-bearing line: {target!r}")
        if target not in lines:
            raise SystemExit(f"{case_id}: map line not present in note: {target!r}")
        idx = lines.index(target)
        if sentences:
            lines[idx] = _remove_sentences(target, sentences, case_id)
        else:
            del lines[idx]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=V2_DEFAULT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    plan = json.loads(MAP_PATH.read_text())
    pairs: dict[str, list[dict]] = plan["pairs"]

    split_rows = {name: _load(V1 / name) for name in FILES[:2]}
    diffs: list[str] = []
    note_by_case: dict[str, str] = {}

    for name in FILES[:2]:
        for row in split_rows[name]:
            stem = _pair_stem(row["case_id"])
            removals = pairs.get(stem, [])
            if not removals:
                note_by_case[row["case_id"]] = _get_note(row)
                continue
            before = _get_note(row)
            after = _scrub_note(before, removals, row["case_id"])
            _set_note(row, after)
            note_by_case[row["case_id"]] = after
            diff = "\n".join(
                difflib.unified_diff(
                    before.split("\n"),
                    after.split("\n"),
                    fromfile=f"v1/{row['case_id']}",
                    tofile=f"v2/{row['case_id']}",
                    lineterm="",
                )
            )
            diffs.append(f"## {row['case_id']}\n\n```diff\n{diff}\n```\n")

    for name in FILES[:2]:
        (args.out / name).write_text("".join(json.dumps(row) + "\n" for row in split_rows[name]))

    # the bundle carries an extra pinned subsumption_codes field per row, so it is
    # scrubbed independently (same map), never rebuilt from the split-file rows.
    bundle_rows = _load(V1 / FILES[2])
    for row in bundle_rows:
        removals = pairs.get(_pair_stem(row["case_id"]), [])
        if removals:
            _set_note(row, _scrub_note(_get_note(row), removals, row["case_id"]))
        if _get_note(row) != note_by_case[row["case_id"]]:
            raise SystemExit(f"{row['case_id']}: bundle/split scrub divergence")
    (args.out / FILES[2]).write_text("".join(json.dumps(row) + "\n" for row in bundle_rows))

    n_changed = len(diffs)
    (args.out / "SCRUB_DIFF.md").write_text(
        f"# SCRUB-1 v1 -> v2 note diff audit\n\n"
        f"Preregistration: OSF {PRE_REG}. Pure-deletion scrub of ungrounded exam/vitals\n"
        f"content; label surfaces byte-identical (see tests/test_scrub_corpus.py).\n"
        f"{n_changed} of {sum(len(r) for r in split_rows.values())} notes changed.\n\n"
        + "\n".join(diffs)
    )
    print(f"scrubbed {n_changed} notes across {len(pairs)} mapped pairs -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
