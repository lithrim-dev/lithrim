"""REL-1 acceptance: the tracked study-reproduction surface (repro/ + REPRODUCING.md + CITATION.cff).

The published study's orchestration inputs were ephemeral or untracked; these tests pin
the tracked, sanitized, parameterized reproduction surface a stranger clones.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
REPRO = REPO / "repro"
SCRIPTS = ["setup_streams.py", "cohort_runner.py", "consolidate.py", "scrub_corpus.py"]
CORPUS_FILES = [
    "corpus/cv_bidirectional_44_bundle.jsonl",
    "corpus/upcoded_positives.jsonl",
    "corpus/clean_generalization_negatives.jsonl",
    # SCRUB-1 (preregistered F10 correction, OSF 10.17605/OSF.IO/2ZU4H): the scrubbed
    # v2 corpus + its audit surfaces carry the same sanitization guarantee as v1.
    "corpus_v2/cv_bidirectional_44_bundle.jsonl",
    "corpus_v2/upcoded_positives.jsonl",
    "corpus_v2/clean_generalization_negatives.jsonl",
    "corpus_v2/scrub_map.json",
    "corpus_v2/SCRUB_DIFF.md",
]
ONTOLOGY_FILES = ["ontology_armT.json", "ontology_armR.json"]
ZENODO_DOI = "10.5281/zenodo.21270268"
ZENODO_CONCEPT_DOI = "10.5281/zenodo.21270267"
OSF_DOI = "10.17605/OSF.IO/2ZU4H"


# --- A1a: scripts carry no machine-local or study-second-stack hardcodes ---


@pytest.mark.parametrize("script", SCRIPTS)
def test_repro_scripts_have_no_local_hardcodes(script):
    text = (REPRO / script).read_text()
    assert "/Users/" not in text, f"{script} hardcodes a home directory"
    assert "/private/tmp" not in text, f"{script} hardcodes an ephemeral scratch path"
    assert ":18787" not in text, f"{script} hardcodes the study's second stack port"


# --- A1b: sanitized data files (no physician name, no facility name) ---


# REL-5f (final-gate B2): the name/facility needles come from the UNTRACKED local file
# (.release_needles.json; integrity-pinned in tests/_needles.py) — no decodable form may
# live in tracked source. The sweep skips where the local file is absent.


@pytest.mark.parametrize("relpath", CORPUS_FILES + ONTOLOGY_FILES + ["role_binds.json"])
def test_repro_data_is_sanitized(relpath):
    from tests._needles import require_needle

    name = require_needle("collaborator")
    facility = require_needle("facility")
    text = (REPRO / relpath).read_text()
    assert name not in text, f"{relpath} leaks the physician collaborator's name"
    assert facility not in text, f"{relpath} leaks a facility name"


# --- A1c: REPRODUCING.md exists and carries both DOIs ---


def test_reproducing_md_exists_with_both_dois():
    md = (REPO / "REPRODUCING.md").read_text()
    assert ZENODO_DOI in md, "REPRODUCING.md missing the Zenodo report DOI"
    assert OSF_DOI in md, "REPRODUCING.md missing the OSF prereg DOI"


# --- A1d: CITATION.cff parses as YAML and carries the Zenodo DOI ---


def test_citation_cff_parses_and_cites_the_report():
    yaml = pytest.importorskip("yaml")
    raw = (REPO / "CITATION.cff").read_text()
    doc = yaml.safe_load(raw)
    assert doc.get("cff-version"), "CITATION.cff missing cff-version"
    assert ZENODO_DOI in raw, "CITATION.cff missing the Zenodo report DOI"
    authors = doc.get("authors") or []
    assert any(a.get("family-names") == "Gaur" for a in authors), "author record missing"


# --- A1e: the 44-case bundle is intact (44 rows, pinned SNOMED codes on every row) ---


def test_bundle_is_44_rows_with_subsumption_codes():
    rows = [
        json.loads(line)
        for line in (REPRO / "corpus/cv_bidirectional_44_bundle.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert len(rows) == 44, f"bundle rows {len(rows)} != 44"
    missing = [r.get("case_id") for r in rows if not r.get("subsumption_codes")]
    assert not missing, f"rows missing subsumption_codes: {missing}"


def test_split_files_are_22_rows_each():
    for name in ("corpus/upcoded_positives.jsonl", "corpus/clean_generalization_negatives.jsonl"):
        rows = [line for line in (REPRO / name).read_text().splitlines() if line.strip()]
        assert len(rows) == 22, f"{name} rows {len(rows)} != 22"


# --- A2: setup_streams.py --dry-run exits 0 offline, prints the plan, makes no HTTP call ---


def test_setup_streams_dry_run_is_offline_and_prints_the_plan():
    env = dict(os.environ)
    # An unroutable base: any attempted HTTP call fails loudly -> nonzero exit.
    env["LITHRIM_REPRO_BASE"] = "http://127.0.0.1:9"
    proc = subprocess.run(
        [sys.executable, str(REPRO / "setup_streams.py"), "--dry-run"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        cwd=str(REPO),
    )
    assert proc.returncode == 0, f"dry-run exited {proc.returncode}: {proc.stderr[:800]}"
    out = proc.stdout
    for ws in (
        "stream-a-single",
        "stream-b-ensemble",
        "stream-c-same",
        "stream-c-mixed",
        "baseline-scalar-reward",
    ):
        assert ws in out, f"dry-run plan missing workspace {ws}"
    # REL-5e: the script authors the PUBLISHED names, incl. ALL SIX ensemble members
    # (repro/role_binds.json stream_role_binds is the authoritative set).
    for role in (
        "single_generalist",
        "ens_gpt41",
        "ens_gpt5",
        "ens_opus",
        "ens_sonnet",
        "ens_llama",
        "ens_mistral",
        "cs_risk",
        "cm_faith",
        "scalar_reward_baseline",
    ):
        assert role in out, f"dry-run plan missing judge {role}"
    assert "lens" in out.lower(), "dry-run plan does not describe lenses"


# --- A3 (SCRUB-1 rerun seams): corpus dir + workspace-name suffix are parameterizable,
# so the preregistered v2 rerun runs on FRESH workspaces over the SCRUBBED corpus
# without touching the v1 study workspaces (REPRODUCING.md: "a fresh set of workspaces").


def test_setup_streams_dry_run_supports_scrubbed_corpus_and_ws_suffix():
    env = dict(os.environ)
    env["LITHRIM_REPRO_BASE"] = "http://127.0.0.1:9"
    env["LITHRIM_REPRO_CORPUS_DIR"] = str(REPRO / "corpus_v2")
    env["LITHRIM_REPRO_WS_SUFFIX"] = "-v2t"
    proc = subprocess.run(
        [sys.executable, str(REPRO / "setup_streams.py"), "--dry-run"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        cwd=str(REPO),
    )
    assert proc.returncode == 0, f"dry-run exited {proc.returncode}: {proc.stderr[:800]}"
    out = proc.stdout
    for ws in (
        "stream-a-single-v2t",
        "stream-b-ensemble-v2t",
        "stream-c-same-v2t",
        "stream-c-mixed-v2t",
        "baseline-scalar-reward-v2t",
    ):
        assert ws in out, f"dry-run plan missing suffixed workspace {ws}"
    assert "corpus_v2" in out, "dry-run plan not reading the scrubbed corpus dir"


@pytest.mark.parametrize("script", ["cohort_runner.py", "consolidate.py"])
def test_run_scripts_honor_ws_suffix(script):
    text = (REPRO / script).read_text()
    assert "LITHRIM_REPRO_WS_SUFFIX" in text, (
        f"{script} missing the workspace-suffix seam the v2 rerun needs"
    )


# --- A4: the tracked tree references the paper (README + REPRODUCING + CITATION) ---


@pytest.mark.parametrize("relpath", ["README.md", "REPRODUCING.md", "CITATION.cff"])
def test_tracked_tree_references_the_report_doi(relpath):
    assert ZENODO_DOI in (REPO / relpath).read_text(), f"{relpath} missing {ZENODO_DOI}"


def test_readme_research_section_links_prereg_and_reproducing():
    md = (REPO / "README.md").read_text()
    assert OSF_DOI in md, "README missing the OSF prereg DOI"
    assert ZENODO_CONCEPT_DOI in md, "README missing the Zenodo concept DOI"
    assert "REPRODUCING.md" in md, "README missing the REPRODUCING.md pointer"
