"""SCRUB-1 acceptance: the preregistered F10 corpus correction (OSF 10.17605/OSF.IO/2ZU4H).

The prereg binds the scrub: regenerate the 44 MTS notes (22 clean-generalization + 22
upcode twins) with all note content not grounded in their transcript removed — the canned
exam phrases, synthesized vitals blocks, and examination-maneuver findings — while every
label-bearing surface (transcript, PMH diagnosis lines, pinned SNOMED codes, injection
recipes, expected flags) stays byte-identical to v1. cv_mts_163 carries no detectable
unsupported content and must emerge unchanged. The scrub is pure deletion: no token may
be introduced. The scrubbed corpus ships as repro/corpus_v2/ with a per-case diff audit
so the v1->v2 delta is independently reviewable (deposited with Zenodo v2).
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
V1 = REPO / "repro" / "corpus"
V2 = REPO / "repro" / "corpus_v2"
SCRUBBER = REPO / "repro" / "scrub_corpus.py"
MAP = V2 / "scrub_map.json"
DIFF_AUDIT = V2 / "SCRUB_DIFF.md"
FILES = [
    "clean_generalization_negatives.jsonl",
    "upcoded_positives.jsonl",
    "cv_bidirectional_44_bundle.jsonl",
]
UNCHANGED_PAIR = "cv_mts_163"
CANNED_PHRASES = [
    "No acute distress",
    "no acute distress",
    "Vital signs stable",
    "Vitals stable",
    "Alert and oriented",
]
_SECTION_PREFIX = re.compile(r"^(\s*[A-Za-z][A-Za-z0-9 /()]*:\s*)")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?]) +")


def _load(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _note(row):
    doc = row["artifacts"][0]["content"]
    if isinstance(doc, str):
        doc = json.loads(doc)
    return doc["content"][0]["attachment"]["data"]


def _wrapper_without_note(row):
    doc = row["artifacts"][0]["content"]
    if isinstance(doc, str):
        doc = json.loads(doc)
    doc = json.loads(json.dumps(doc))
    doc["content"][0]["attachment"]["data"] = ""
    return doc


def _pair_stem(case_id):
    return re.sub(r"_(clean_generalization|upcode)_", "_PAIR_", case_id)


def _split_line(line):
    m = _SECTION_PREFIX.match(line)
    prefix = m.group(1) if m else ""
    return prefix, [s for s in _SENTENCE_SPLIT.split(line[len(prefix) :]) if s]


def _rows(version, name):
    root = V1 if version == 1 else V2
    path = root / name
    if not path.exists():
        pytest.fail(f"{path.relative_to(REPO)} missing — run repro/scrub_corpus.py")
    return _load(path)


@pytest.fixture(scope="module")
def corpora():
    v1 = {name: _rows(1, name) for name in FILES}
    v2 = {name: _rows(2, name) for name in FILES}
    return v1, v2


def _paired(v1, v2, name):
    return list(zip(v1[name], v2[name], strict=True))


# --- surface: files exist, shape and order preserved ---


def test_v2_surface_exists():
    for artifact in [SCRUBBER, MAP, DIFF_AUDIT, *(V2 / f for f in FILES)]:
        assert artifact.exists(), f"{artifact.relative_to(REPO)} missing"


def test_v2_shape_and_order(corpora):
    v1, v2 = corpora
    for name in FILES:
        assert [r["case_id"] for r in v2[name]] == [r["case_id"] for r in v1[name]]
    bundle = {}
    for row in v2[FILES[2]]:
        row = dict(row)
        # v1 invariant: bundle rows carry the extra pinned subsumption_codes field
        row.pop("subsumption_codes", None)
        bundle[row["case_id"]] = json.dumps(row, sort_keys=True)
    parts = {r["case_id"]: json.dumps(r, sort_keys=True) for r in v2[FILES[0]] + v2[FILES[1]]}
    assert bundle == parts, "v2 bundle rows must match the v2 split files"


# --- label surfaces: everything except the note text is byte-identical ---


def test_non_note_fields_byte_identical(corpora):
    v1, v2 = corpora
    for name in FILES:
        for r1, r2 in _paired(v1, v2, name):
            for key in r1:
                if key == "artifacts":
                    continue
                assert r2[key] == r1[key], f"{r1['case_id']}: field {key} drifted"
            assert _wrapper_without_note(r2) == _wrapper_without_note(r1), (
                f"{r1['case_id']}: FHIR wrapper drifted beyond attachment.data"
            )


def test_pmh_block_byte_identical(corpora):
    v1, v2 = corpora
    for name in FILES[:2]:
        for r1, r2 in _paired(v1, v2, name):
            v2_lines = _note(r2).splitlines()
            for line in _note(r1).splitlines():
                if re.match(r"^\s*-\s+\S", line) or re.match(
                    r"^(PMH|PAST MEDICAL HISTORY)\b", line
                ):
                    assert line in v2_lines, (
                        f"{r1['case_id']}: label-bearing line removed: {line!r}"
                    )


def test_twin_diff_invariant(corpora):
    v1, v2 = corpora

    def twin_delta(rows_clean, rows_up):
        clean = {_pair_stem(r["case_id"]): _note(r) for r in rows_clean}
        up = {_pair_stem(r["case_id"]): _note(r) for r in rows_up}
        return {
            stem: (
                sorted(set(clean[stem].splitlines()) - set(up[stem].splitlines())),
                sorted(set(up[stem].splitlines()) - set(clean[stem].splitlines())),
            )
            for stem in clean
        }

    assert twin_delta(v2[FILES[0]], v2[FILES[1]]) == twin_delta(v1[FILES[0]], v1[FILES[1]]), (
        "scrub must apply identically to both twins (only the PMH concept line differs)"
    )


# --- pure deletion: no token introduced, order preserved ---


def test_pure_deletion(corpora):
    v1, v2 = corpora
    for name in FILES[:2]:
        for r1, r2 in _paired(v1, v2, name):
            v1_lines = _note(r1).splitlines()
            cursor = 0
            for line in _note(r2).splitlines():
                matched = False
                while cursor < len(v1_lines):
                    candidate = v1_lines[cursor]
                    cursor += 1
                    if line == candidate:
                        matched = True
                        break
                    # the scrubber emits v1-prefix + join(kept sentences), so judge the
                    # v2 line against the V1 line's prefix (the kept remainder may itself
                    # start with a "Label:" that was mid-line in v1)
                    p1, s1 = _split_line(candidate)
                    if line.startswith(p1):
                        s2 = [s for s in _SENTENCE_SPLIT.split(line[len(p1) :]) if s]
                        if s2 and _is_subsequence(s2, s1):
                            matched = True
                            break
                assert matched, (
                    f"{r1['case_id']}: v2 line not derivable from v1 by deletion: {line!r}"
                )


def _is_subsequence(sub, seq):
    it = iter(seq)
    return all(s in it for s in sub)


# --- the registered categories are gone ---


def test_no_ungrounded_vitals_numbers(corpora):
    v1, v2 = corpora
    vitals = re.compile(r"\b\d{2,3}/\d{2,3}\b|\b3[5-9]\.\d\b")
    for name in FILES[:2]:
        for _, r2 in _paired(v1, v2, name):
            transcript = r2["transcript"]
            for token in vitals.findall(_note(r2)):
                assert token in transcript, (
                    f"{r2['case_id']}: vitals value {token!r} not grounded in transcript"
                )


def test_no_canned_phrases_without_declared_exception(corpora):
    _, v2 = corpora
    exceptions = json.loads(MAP.read_text()).get("exceptions", {})
    for name in FILES[:2]:
        for r2 in v2[name]:
            stem = _pair_stem(r2["case_id"])
            allowed = {e["phrase"] for e in exceptions.get(stem, [])}
            for phrase in CANNED_PHRASES:
                if phrase in _note(r2) and phrase not in allowed:
                    pytest.fail(
                        f"{r2['case_id']}: canned phrase {phrase!r} survived without a "
                        f"justified exception in scrub_map.json"
                    )


# --- prereg manipulation checks ---


def test_cv_mts_163_pair_unchanged(corpora):
    v1, v2 = corpora
    for name in FILES[:2]:
        for r1, r2 in _paired(v1, v2, name):
            if _pair_stem(r1["case_id"]).startswith(UNCHANGED_PAIR):
                assert _note(r2) == _note(r1), (
                    f"{r1['case_id']}: prereg says this case carries no unsupported "
                    f"content — it must emerge byte-identical"
                )


def test_all_other_pairs_scrubbed(corpora):
    v1, v2 = corpora
    changed = set()
    for name in FILES[:2]:
        for r1, r2 in _paired(v1, v2, name):
            if _note(r2) != _note(r1):
                changed.add(_pair_stem(r1["case_id"]))
    expected = {
        _pair_stem(r["case_id"])
        for r in v1[FILES[0]]
        if not _pair_stem(r["case_id"]).startswith(UNCHANGED_PAIR)
    }
    assert changed == expected, (
        "prereg: 21 of 22 pairs carry the artifact — exactly those must change "
        f"(missing: {sorted(expected - changed)}, unexpected: {sorted(changed - expected)})"
    )


# --- auditability: the map accounts for every edit, the diff sheet covers every case ---


def test_map_accounts_for_every_edit(corpora):
    v1, v2 = corpora
    plan = json.loads(MAP.read_text())["pairs"]
    for name in FILES[:2]:
        for r1, r2 in _paired(v1, v2, name):
            stem = _pair_stem(r1["case_id"])
            removed_lines = {e["line"] for e in plan.get(stem, []) if not e.get("sentences")}
            edited_lines = {e["line"] for e in plan.get(stem, []) if e.get("sentences")}
            v1_lines, v2_lines = _note(r1).splitlines(), _note(r2).splitlines()
            gone = [ln for ln in v1_lines if ln not in v2_lines]
            for line in gone:
                assert line in removed_lines or line in edited_lines, (
                    f"{r1['case_id']}: line changed outside the scrub map: {line!r}"
                )


def test_diff_audit_covers_changed_cases(corpora):
    v1, v2 = corpora
    audit = DIFF_AUDIT.read_text()
    for name in FILES[:2]:
        for r1, r2 in _paired(v1, v2, name):
            if _note(r2) != _note(r1):
                assert r1["case_id"] in audit, f"{r1['case_id']} missing from SCRUB_DIFF.md"


# --- determinism: the scrubber regenerates the committed output byte-for-byte ---


def test_scrubber_reproduces_committed_output(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRUBBER), "--out", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert result.returncode == 0, result.stderr
    for name in FILES:
        regenerated = (tmp_path / name).read_bytes()
        committed = (V2 / name).read_bytes()
        assert regenerated == committed, f"{name}: scrubber output drifted from committed v2"
