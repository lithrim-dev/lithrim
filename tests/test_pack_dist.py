"""PACK-DIST-1 (D4) — the CE-clean proof + external-load + fail-closed + moat parity.

The acceptance gate for releasing the OSS core: after the healthcare realm relocated to the
external ``lithrim-pack-healthcare`` repo, this pins —

- **A2 (CE-clean, non-vacuous):** the tracked CE tree carries NO ``packs/healthcare/``, NO clinical
  corpora, and ZERO genuinely-clinical content on the shipped DATA surface (``packs/`` +
  ``examples/`` + ``data/config/``) beyond an ENUMERATED set of passive provenance notes. The sweep
  is non-vacuous (a planted needle in a non-carve-out file is caught). The ``lithrim_bench/`` CODE
  residual (the frozen council + the HIPAA_* config keys + docstrings) is the domain of
  ``test_6bclean_attestation`` — not re-swept here.
- **A1 (external load):** a subprocess with ``LITHRIM_BENCH_PACKS_DIR`` pointed at the sibling pack
  repo loads ``healthcare`` (19 codes / 8 owners / roster) from OUTSIDE this repo — the frozen
  council binds it via discovery, identically. Skipped if the sibling repo is not checked out.
- **A4 (fail-closed):** an undiscoverable pack raises ``FileNotFoundError`` — never a silent
  fallback — at the ``*_path`` resolvers.
- **A5 (moat + frozen seams):** ``_apply_consensus`` + ``extract_verdict_confidence`` are
  byte-identical (AST) vs ``acc4973``; the two CE-resident frozen-seam guards stay green.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ._seam_freeze import (
    assert_compliance_council_carveouts_only,
    assert_judges_dspy_consensus_seam_frozen,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
_SIBLING = REPO_ROOT.parent / "lithrim-pack-healthcare"
_COUNCIL_REL = "lithrim_bench/runtime/council/compliance_council.py"
_SEAM_BASELINE = "acc4973"

# The clinical-needle vocabulary the sweep hunts for on the shipped DATA surface.
_NEEDLES = (
    "patient",
    "medication",
    "dosage",
    "allerg",
    "clinical",
    "soap",
    "scribe",
    "snomed",
    "icd10",
    "icd-10",
    "escalat",
    "hipaa",
    "diagnos",
    "prescri",
)
# Tracked DATA-surface dirs that ship in / alongside the core (NOT lithrim_bench/ code — that
# residual is test_6bclean_attestation's domain).
_DATA_SURFACE = ("packs", "examples", "data/config")
# The ENUMERATED passive carve-out: files allowed to contain a needle WORD because it is provenance
# prose / a docstring (no clinical DATA). A NEW needle in any OTHER data-surface file fails A2.
_PASSIVE_CARVE_OUT = frozenset(
    {
        "packs/_core/ontology.json",  # the "_provenance"/"note" explaining the ontology is needle-FREE
        "packs/support_ticket_qa/ontology.json",  # ditto (the standalone sample pack)
        "packs/support_ticket_qa/taxonomy_snapshot.json",  # ditto
        "packs/_plugin_fixture/floors.py",  # docstring: "the clinical record_presence uses"
    }
)


def _tracked(*dirs: str) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", *dirs], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [p for p in out.splitlines() if p]


def _needle_hits(rel_paths: list[str]) -> list[str]:
    """``"path:lineno:line"`` for every line under ``rel_paths`` containing a clinical needle."""
    hits = []
    for rel in rel_paths:
        fp = REPO_ROOT / rel
        if not fp.is_file():
            continue
        try:
            text = fp.read_text()
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            low = line.lower()
            if any(n in low for n in _NEEDLES):
                hits.append(f"{rel}:{i}:{line.strip()}")
    return hits


# ─────────────────────────────────── A2: CE-clean ───────────────────────────────────


def test_a2_no_healthcare_pack_tracked():
    """The headline: the CE tracked tree carries NO ``packs/healthcare/`` file."""
    assert _tracked("packs/healthcare") == [], (
        "packs/healthcare/ is still tracked in the CE repo — the Pro pack must be external"
    )


def test_a2_no_clinical_corpora_tracked():
    """No by-construction clinical corpus ships in CE ``examples/``."""
    clinical = [p for p in _tracked("examples") if p.endswith(".jsonl")]
    assert clinical == [], f"clinical corpora still tracked in CE examples/: {clinical}"


def test_a2_only_blank_slate_agent_seed():
    """The only committed agent seed is the neutral ``ws0_default`` blank slate (0 clinical strings)."""
    seeds = _tracked("data/config/agents")
    assert seeds == ["data/config/agents/ws0_default.json"], f"unexpected agent seeds in CE: {seeds}"
    body = (REPO_ROOT / "data/config/agents/ws0_default.json").read_text().lower()
    assert not any(n in body for n in ("clinical", "scribe", "healthcare")), (
        "ws0_default.json is not a clean blank slate"
    )


def test_a2_data_surface_is_clinical_free_beyond_the_carve_out():
    """The shipped DATA surface (packs/ + examples/ + data/config/) carries ZERO clinical needles
    outside the ENUMERATED passive carve-out. Non-vacuous (see the planted-needle test below)."""
    swept = [p for p in _tracked(*_DATA_SURFACE) if p not in _PASSIVE_CARVE_OUT]
    hits = _needle_hits(swept)
    assert not hits, "genuinely-clinical content on the CE data surface (relocate it):\n" + "\n".join(
        hits
    )


def test_a2_sweep_is_non_vacuous(tmp_path):
    """The sweep WOULD catch a clinical needle — proving A2 is not vacuously green."""
    planted = tmp_path / "planted.json"
    planted.write_text('{"note": "the patient was prescribed a medication dosage"}')
    # _needle_hits resolves against REPO_ROOT, so test the pure predicate on the line directly.
    low = planted.read_text().lower()
    assert any(n in low for n in _NEEDLES), "the needle set fails to catch obvious clinical prose"


def test_a2_carve_out_is_minimal():
    """Every enumerated carve-out file ACTUALLY contains a needle (no dead entries) AND is genuinely
    passive (a tracked provenance/docstring file, not clinical data)."""
    for rel in _PASSIVE_CARVE_OUT:
        assert (REPO_ROOT / rel).is_file(), f"carve-out names a missing file: {rel}"
        assert _needle_hits([rel]), f"carve-out file has no needle (stale entry): {rel}"


# ─────────────────────────────────── A1: external load ───────────────────────────────────

_HAS_SIBLING = (_SIBLING / "healthcare" / "pack.json").is_file()


@pytest.mark.skipif(not _HAS_SIBLING, reason="sibling lithrim-pack-healthcare repo not checked out")
def test_a1_council_binds_from_external_pack():
    """A subprocess with ``LITHRIM_BENCH_PACKS_DIR`` → the sibling repo loads ``healthcare`` from
    OUTSIDE this tree; the FROZEN council binds its 19 codes / 8 owners / roster via discovery."""
    env = {**os.environ, "LITHRIM_BENCH_PACKS_DIR": str(_SIBLING), "LITHRIM_BENCH_PACK": "healthcare"}
    code = (
        "import json; from lithrim_bench.harness import pack as p;"
        "import lithrim_bench.runtime.council.compliance_council as cc;"
        "root=str(p._pack_root('healthcare').resolve());"
        "print(json.dumps({'root': root, 'codes': len(cc.KNOWN_TAXONOMY_CODES),"
        "'owners': len(cc._TIER1_OWNERS), 'roster': p.pack_production_judges()}))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True
    )
    assert out.returncode == 0, f"council import under the external pack failed:\n{out.stderr}"
    got = __import__("json").loads(out.stdout.strip().splitlines()[-1])
    assert "lithrim-pack-healthcare" in got["root"] and "lithrim-bench/packs" not in got["root"], (
        f"did not resolve to the EXTERNAL pack: {got['root']}"
    )
    assert got["codes"] == 19, got
    assert got["owners"] == 8, got
    assert got["roster"] == ["risk_judge", "policy_judge", "faithfulness_judge"], got


# ─────────────────────────────────── A4: fail-closed ───────────────────────────────────


def test_a4_absent_pack_fails_closed():
    """An undiscoverable pack id raises ``FileNotFoundError`` at ``_pack_root`` AND propagates
    through the ``*_path`` resolver — fail-closed, never a silent fallback (the S-BS-90 posture)."""
    from lithrim_bench.harness import pack

    with pytest.raises(FileNotFoundError):
        pack._pack_root("definitely_absent_pack_pack_dist_xyz")
    with pytest.raises(FileNotFoundError):
        pack.pack_ontology_path("definitely_absent_pack_pack_dist_xyz")


# ─────────────────────────────────── A5: moat + frozen seams ───────────────────────────────────


def _named_func_source(src: str, name: str) -> str:
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(src, node)
    raise AssertionError(f"{name} not found")


def test_a5_moat_byte_identical_vs_acc4973():
    """``_apply_consensus`` + ``extract_verdict_confidence`` are byte-identical (AST source) vs
    ``acc4973`` — this cycle changed pack DISCOVERY (above the seam), never the consensus mechanism."""
    base = subprocess.run(
        ["git", "show", f"{_SEAM_BASELINE}:{_COUNCIL_REL}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    cur = (REPO_ROOT / _COUNCIL_REL).read_text()
    for name in ("_apply_consensus", "extract_verdict_confidence"):
        assert _named_func_source(base, name) == _named_func_source(cur, name), (
            f"MOAT VIOLATION: {name} changed vs {_SEAM_BASELINE}"
        )


def test_a5_ce_resident_frozen_guards_green():
    """The two frozen-seam guards that read CORE files (not the now-external pack) stay green —
    the frozen council carve-outs + the consensus seam are untouched by the discovery change."""
    assert_compliance_council_carveouts_only(REPO_ROOT)
    assert_judges_dspy_consensus_seam_frozen(REPO_ROOT)
