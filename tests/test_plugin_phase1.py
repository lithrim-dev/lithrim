"""PLUGIN-1 — the Plugin Phase-1 registry-unification parity proof.

The cycle is a PURE REFACTOR: the three ad-hoc registries (pack loaders / the grounding
contract registry / the judge provider) are folded onto one declared plugin manifest + a
load-time ``tier`` gate, and grading must be **byte-identical by default**. This module pins:

- **A1 parity (value-equality):** under the permit-all default, the merged contract registries
  ``suppress_executors()`` / ``floor_executors()`` value-equal an EXPLICIT expected snapshot, and
  ``contract_plugins()`` enumerates exactly them (no drift) — the R1 refinement.
- **A2 gate non-vacuity (subprocess):** a ``tier: pro`` pack under ``LITHRIM_BENCH_LICENSE=deny-all``
  is ABSENT — the harness import fails closed with ``PackLicenseError`` (not stubbed); ``core``
  always loads even under deny; the permit-all default loads the pro pack (byte-identical).
- **A3 provenance:** ``provenance_snapshot()`` records the loaded set + tier; the additive
  ``PipelineProvenance`` fields round-trip through ``model_dump`` (auto-persist); a denied plugin
  is absent from the snapshot (the per-plugin skip).
- **A4 open/closed (subprocess):** a NET-NEW fixture ``contract`` plugin is picked up via the pack
  manifest + ``floors.py`` ALONE — ZERO edits to ``grounding.py`` / ``judges_dspy.py`` / the council.
- **A5 frozen-seam + moat:** the three seam guards stay green; ``_apply_consensus`` +
  ``extract_verdict_confidence`` are byte-identical (AST-extracted) vs ``acc4973``; ``signals.py`` /
  ``withstands.py`` are unchanged vs the PLUGIN-1 parent (D-2: they post-date ``acc4973``, so the
  honest pin is 0-diff vs parent, not vs ``acc4973``).

Subprocess (not in-process) wherever the LICENSE/PACK env must bite, because the active pack is
resolved at module import (``harness/ontology.py`` ``DEFAULT_ONTOLOGY_PATH = pack_ontology_path()``)
— the ``test_pack_layer1b.py`` precedent.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from lithrim_bench.harness import grounding as G
from lithrim_bench.harness import pack as PK
from lithrim_bench.harness import plugins as P

REPO_ROOT = Path(__file__).resolve().parents[1]
# PACK-DIST self-containment: the A1/A2/A3 parity assertions run against PUBLIC in-repo fixture
# packs instead of the external ``healthcare`` Pro pack, so they are green with the pack absent.
# ``_core`` (the neutral core-tier default) anchors the core-only registry parity + a core-tier
# provenance snapshot; ``_plugin_fixture`` (a public ``tier: pro`` fixture pack, already used by
# A2/A4 below) anchors the assertions that STRUCTURALLY need a pro pack (the gate raise + a pro
# plugin present to be per-plugin-denied). The MECHANISMS are identical — only the pack + its
# real codes differ.
_CORE_PACK = "_core"
_COUNCIL_REL = "lithrim_bench/runtime/council/compliance_council.py"
_SEAM_BASELINE = (
    "acc4973"  # the moat AST-identity baseline (_apply_consensus / extract_verdict_confidence)
)
# D-2: signals.py / withstands.py are NET-NEW after acc4973 (landed 8cb388b / d9a5bb0), so
# "byte-identical vs acc4973" is ill-defined for them. The honest moat pin for THIS cycle is
# byte-identity vs the PLUGIN-1 parent (the commit before D1) — the baseline constant
# (``_PLUGIN1_PARENT``) and the dual-mode attestation live in tests/_seam_freeze.py (S-REL-19).
_FIXTURE_PACK = "_plugin_fixture"


# ─────────────────────────── A1 — parity by value-equality (R1) ───────────────────────────

# The EXPLICIT expected registry snapshot under the neutral ``_core`` pack (self-contained: no
# external Pro pack needed). ``_core`` is ``tier: core`` with NO ``floors`` module, so the merged
# registries are exactly the CORE-generic executors — every entry is ``tier: core`` (the pro
# clinical executors record_presence/snomed_subsumption/dosage_grounding/concept_preservation are
# healthcare-only and correctly ABSENT here). Value-equality against this EXPLICIT set — not "no
# exception" — is what makes A1 non-vacuous (R1).
_EXPECTED_SUPPRESS = {
    "presence_check",
    "kb_grounding",
    # CONN-WEBSEARCH-1: non-authoritative-by-construction web-search suppress (never clears).
    "web_search",
    # GROUND-FLOOR-SOURCE-1: the core-generic answer⊆source faithfulness suppress executor.
    "source_grounding",
    # TOOL-AUTHOR-1: the generic authored-MCP-tool suppress executor (advisory/corroborated).
    "mcp_call",
    # LAYER2-SUPPRESS-1: the core-generic evidence-integrity suppress executor (span-level).
    "evidence_presence",
    # REPRO-1 R4c: the core-generic terminology-subsumption suppress (span-driven, tool-driven).
    "terminology_subsumption",
    # FLOOR-BATTERY-1: the core-generic ordered terminology battery (validity/mislabel/category/is-a).
    "snomed_battery",
}
# CORE-FLOOR-1: value_presence is a CORE floor (domain-agnostic completeness floor).
# REPRO-1 R4a/R4b: fact_preservation + speaker_attribution are the core bounded-extraction floors.
_EXPECTED_FLOOR = {"structural_jute", "jute_gen", "value_presence",
                   "fact_preservation", "speaker_attribution"}
_EXPECTED_CONTRACT_PLUGINS = {
    "presence_check": ("contract", "core", "in_process", "grounding.suppress"),
    "kb_grounding": ("contract", "core", "service", "grounding.suppress"),
    # GROUND-FLOOR-SOURCE-1: core, pure-stdlib (in_process), answer⊆source suppress executor.
    "source_grounding": ("contract", "core", "in_process", "grounding.suppress"),
    # CONN-WEBSEARCH-1: core, service-transport (:8585), non-authoritative suppress.
    "web_search": ("contract", "core", "service", "grounding.suppress"),
    # TOOL-AUTHOR-1: core generic authored-MCP-tool suppress (builds its own McpStdioClient).
    "mcp_call": ("contract", "core", "in_process", "grounding.suppress"),
    # LAYER2-SUPPRESS-1: core, pure-stdlib (in_process), evidence-integrity suppress executor.
    "evidence_presence": ("contract", "core", "in_process", "grounding.suppress"),
    # REPRO-1 R4c: core generic terminology subsumption (builds its own McpStdioClient, like mcp_call).
    "terminology_subsumption": ("contract", "core", "in_process", "grounding.suppress"),
    # FLOOR-BATTERY-1: core generic ordered terminology battery (builds its own McpStdioClient).
    "snomed_battery": ("contract", "core", "in_process", "grounding.suppress"),
    "structural_jute": ("contract", "core", "service", "grounding.floor"),
    "jute_gen": ("contract", "core", "service", "grounding.floor"),
    "value_presence": ("contract", "core", "in_process", "grounding.floor"),
    # REPRO-1 R4a/R4b: the core bounded-extraction floors (LM via the provider seam, in_process).
    "fact_preservation": ("contract", "core", "in_process", "grounding.floor"),
    "speaker_attribution": ("contract", "core", "in_process", "grounding.floor"),
}


def test_a1_merged_registries_value_equal_the_expected_snapshot(monkeypatch):
    """A1: under the neutral ``_core`` pack, the merged suppress/floor registries equal the EXPLICIT
    expected sets — the pure refactor did not change the registry contents. Self-contained: pins the
    active pack to ``_core`` (no external Pro pack), so it is green with healthcare absent."""
    monkeypatch.setenv("LITHRIM_BENCH_PACK", _CORE_PACK)
    assert set(G.suppress_executors()) == _EXPECTED_SUPPRESS
    assert set(G.floor_executors()) == _EXPECTED_FLOOR


def test_a1_contract_plugins_enumerate_exactly_the_merge(monkeypatch):
    """A1: ``contract_plugins()`` declares exactly the merged registry — same ids, with the
    expected kind/tier/transport/implements (under ``_core`` every executor is tier=core), and the
    enumeration ids == ``suppress_executors() ∪ floor_executors()`` (non-vacuous, no drift).
    Self-contained: pins the active pack to ``_core``."""
    monkeypatch.setenv("LITHRIM_BENCH_PACK", _CORE_PACK)
    got = {p.id: (p.kind, p.tier, p.transport, p.implements) for p in G.contract_plugins()}
    assert got == _EXPECTED_CONTRACT_PLUGINS
    assert set(got) == set(G.suppress_executors()) | set(G.floor_executors())


def test_a1_provider_plugins_are_declared_core():
    """A1: the provider registry declares Azure + BYO-Claude + the composo reward model as core
    kind:provider plugins (F8-PROVIDER: the reward-model judge slot is manifest-declared too)."""
    prov = {p.id: (p.kind, p.tier) for p in P.provider_plugins()}
    assert prov == {
        "azure_openai": ("provider", "core"),
        "byo_claude": ("provider", "core"),
        "composo": ("provider", "core"),
    }


# ─────────────────────────── A2 — the load-time tier gate (non-vacuous) ───────────────────────────


def _subproc(code: str, *, pack: str | None = None, license: str | None = None):
    run_env = dict(os.environ)
    if pack is not None:
        run_env["LITHRIM_BENCH_PACK"] = pack
    if license is not None:
        run_env["LITHRIM_BENCH_LICENSE"] = license
    else:
        run_env.pop("LITHRIM_BENCH_LICENSE", None)
    return subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, env=run_env, capture_output=True, text=True
    )


def test_a2_pro_pack_under_permit_all_loads():
    """A2: the permit-all default (no LICENSE env) loads the tier:pro fixture pack — byte-identical
    to before the gate existed."""
    out = _subproc(
        "from lithrim_bench.harness import pack as PK; print(PK.pack_ontology_path()); print('LOADED')",
        pack=_FIXTURE_PACK,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().splitlines()[-1] == "LOADED"


def test_a2_pro_pack_under_deny_is_absent():
    """A2 (the non-vacuity): the tier:pro fixture pack under ``deny-all`` is ABSENT — the harness
    import itself fails closed with PackLicenseError (not stubbed, not silently downgraded)."""
    out = _subproc(
        "from lithrim_bench.harness import pack as PK; PK.pack_ontology_path(); print('LOADED')",
        pack=_FIXTURE_PACK,
        license="deny-all",
    )
    assert out.returncode != 0, "a denied pro pack must fail closed, not load"
    assert "PackLicenseError" in out.stderr
    assert "LOADED" not in out.stdout


def test_a2_core_pack_under_deny_still_loads():
    """A2: ``core`` is never gated — ``_core`` loads even under ``deny-all`` (only ``pro`` is gated)."""
    out = _subproc(
        "from lithrim_bench.harness import pack as PK; print(PK.pack_ontology_path()); print('LOADED')",
        pack="_core",
        license="deny-all",
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().splitlines()[-1] == "LOADED"


def test_a2_gate_keyed_to_pro_only():
    """The gate predicate: only ``pro`` requires a license; core/fixture/demo never do. Self-contained:
    the pro-tier raise is proven on the PUBLIC in-repo ``_plugin_fixture`` (tier: pro) pack instead of
    the external healthcare pack — the MECHANISM (a pro pack raises under deny, clears under permit) is
    identical, no external pack needed."""
    assert P.is_gated("pro")
    assert not any(P.is_gated(t) for t in ("core", "fixture", "demo"))
    # a pro-tier pack under permit-all does not raise; under deny it does
    PK.assert_pack_licensed(_FIXTURE_PACK, P.License("permit-all"))
    with pytest.raises(PK.PackLicenseError):
        PK.assert_pack_licensed(_FIXTURE_PACK, P.License("deny-all"))


def test_a2_license_grammar():
    """The License env grammar (the gate's lever)."""
    lic = P.License.from_env
    assert lic({}).permits("healthcare") is True  # unset → permit-all
    assert lic({"LITHRIM_BENCH_LICENSE": "deny-all"}).permits("healthcare") is False
    assert lic({"LITHRIM_BENCH_LICENSE": "denylist:healthcare"}).permits("healthcare") is False
    assert lic({"LITHRIM_BENCH_LICENSE": "denylist:healthcare"}).permits("_core") is True
    assert lic({"LITHRIM_BENCH_LICENSE": "allowlist:healthcare"}).permits("foo") is False
    with pytest.raises(ValueError):
        lic({"LITHRIM_BENCH_LICENSE": "garbage"})


# ─────────────────────────── A3 — provenance records the loaded set ───────────────────────────


def test_a3_provenance_snapshot_records_pack_and_plugins(monkeypatch):
    """A3: under the neutral ``_core`` pack, the snapshot records the active pack + tier + the loaded
    plugin set (the pack itself + the contract plugins + the providers + the core tool). Self-contained:
    pins the active pack to ``_core`` — a core-tier snapshot needs no external Pro pack."""
    monkeypatch.setenv("LITHRIM_BENCH_PACK", _CORE_PACK)
    snap = P.provenance_snapshot()
    assert snap["active_pack"] == _CORE_PACK and snap["pack_tier"] == "core"
    ids = {p["id"] for p in snap["plugins"]}
    assert {
        _CORE_PACK,
        "azure_openai",
        "byo_claude",
        "etlp_jute",
    } <= ids  # pack + providers + tool
    assert ids >= _EXPECTED_SUPPRESS and ids >= _EXPECTED_FLOOR  # the contracts
    kinds = {p["kind"] for p in snap["plugins"]}
    assert kinds == {"pack", "contract", "provider", "tool"}  # TOOL-1 folds in kind:tool


def test_a3_denied_plugin_is_absent_from_the_snapshot(monkeypatch):
    """A3 / R2 skip path: a denylisted pro plugin is ABSENT from the recorded set (the per-plugin
    skip — distinct from the A2 active-pack RAISE). Self-contained: the pro plugin denied is the
    PUBLIC in-repo ``_plugin_fixture`` pack's ``fixture_suppress`` (a pack-contributed, tier=pro
    contract) instead of the clinical ``record_presence`` — the MECHANISM (per-plugin skip of a
    denied pro plugin while core + the permitted pack stay) is identical."""
    monkeypatch.setenv("LITHRIM_BENCH_PACK", _FIXTURE_PACK)
    snap = P.provenance_snapshot(P.License("denylist", frozenset({"fixture_suppress"})))
    ids = {p["id"] for p in snap["plugins"]}
    assert "fixture_suppress" not in ids  # the denied pro plugin is skipped
    assert "presence_check" in ids and _FIXTURE_PACK in ids  # core + the (permitted) pack stay


def test_a3_additive_fields_round_trip_through_model_dump(monkeypatch):
    """A3: the PipelineProvenance fields auto-persist (model_dump) and are default-safe for older
    docs / replay blobs (the orchestrator wiring; a live grade is cost-gated). Self-contained: pins
    the active pack to ``_core`` — the additive-field round-trip is pack-agnostic."""
    monkeypatch.setenv("LITHRIM_BENCH_PACK", _CORE_PACK)
    from datetime import datetime, timezone

    from lithrim_bench.runtime.pipeline.models import PipelineProvenance

    snap = P.provenance_snapshot()
    prov = PipelineProvenance(
        pipeline_run_id="t",
        org_id="o",
        timestamp=datetime.now(timezone.utc),
        request_hash="h",
        stages_executed=[],
        loaded_plugins=snap["plugins"],
        active_pack=snap["active_pack"],
        pack_tier=snap["pack_tier"],
    )
    doc = prov.model_dump(mode="json")
    assert doc["active_pack"] == _CORE_PACK and doc["pack_tier"] == "core"
    assert {p["id"] for p in doc["loaded_plugins"]} == {p["id"] for p in snap["plugins"]}
    # default-safe: an old doc with no plugin keys re-parses cleanly
    old = {
        "pipeline_run_id": "x",
        "org_id": "o",
        "timestamp": "2026-01-01T00:00:00Z",
        "request_hash": "h",
        "stages_executed": [],
    }
    back = PipelineProvenance.model_validate(old)
    assert back.loaded_plugins == [] and back.active_pack is None and back.pack_tier is None


# ─────────────────────────── A4 — open/closed (zero engine edits) ───────────────────────────


def test_a4_new_fixture_contract_picked_up_via_manifest_only():
    """A4 / SPEC §Success Metrics: a NET-NEW ``contract`` plugin (``fixture_suppress``, declared in
    ``packs/_plugin_fixture/floors.py``) is picked up by the engine's ``suppress_executors()`` AND
    ``contract_plugins()`` through the manifest's ``floors`` path ALONE — ZERO edits to
    ``grounding.py`` / ``judges_dspy.py`` / the council. A subprocess so the fixture pack is the
    active pack at import (discovery is active-pack-only — the fixture is otherwise inert)."""
    out = _subproc(
        "from lithrim_bench.harness import grounding as G; "
        "sup=set(G.suppress_executors()); ids={p.id for p in G.contract_plugins()}; "
        "assert 'fixture_suppress' in sup, sorted(sup); "
        "assert 'fixture_suppress' in ids, sorted(ids); "
        "print('PICKED_UP')",
        pack=_FIXTURE_PACK,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().splitlines()[-1] == "PICKED_UP"


def test_a4_fixture_contract_inherits_pack_tier():
    """A4: the fixture contract inherits the fixture pack's tier (pro) in the declaration — the
    Core/Pro line flows from the single ``tier`` field, even for a pack-contributed plugin."""
    out = _subproc(
        "from lithrim_bench.harness import grounding as G; "
        "t={p.id:p.tier for p in G.contract_plugins()}['fixture_suppress']; print(t)",
        pack=_FIXTURE_PACK,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().splitlines()[-1] == "pro"


def test_s_bs_133_pack_declared_service_transport_is_tagged_service():
    """S-BS-133: a pack's ``floors`` module may declare ``SERVICE_CONTRACT_TYPES``; then
    ``contract_plugins()`` tags that contract ``transport=service`` instead of the core default
    ``in_process``. ``_plugin_fixture`` declares ``fixture_suppress`` as service-transport.
    (Declarative metadata only — dispatch is unchanged; no pack ships a real service floor yet.)"""
    out = _subproc(
        "from lithrim_bench.harness import grounding as G; "
        "t={p.id:p.transport for p in G.contract_plugins()}['fixture_suppress']; print(t)",
        pack=_FIXTURE_PACK,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().splitlines()[-1] == "service"


# ─────────────────────────── TOOL-1 — the kind:tool plane ───────────────────────────


def test_tool1_core_tool_declared():
    """TOOL-1: the JUTE connector is declared as a core ``kind: tool`` plugin (the API-connector
    exemplar — always present, never gated; the CE 'configure any API connector' anchor)."""
    tools = {p.id: (p.kind, p.tier, p.transport, p.implements) for p in P.tool_plugins()}
    assert tools.get("etlp_jute") == ("tool", "core", "service", "tool.api_connector")


def test_tool1_provenance_records_the_tool_kind():
    """TOOL-1: ``provenance_snapshot()`` now enumerates ``kind: tool`` (the fold is appended into
    the snapshot + license-filtered like every other kind)."""
    snap = P.provenance_snapshot()
    assert "tool" in {p["kind"] for p in snap["plugins"]}
    assert "etlp_jute" in {p["id"] for p in snap["plugins"]}


def test_tool1_open_closed_pack_tool_via_manifest():
    """TOOL-1 open/closed: a NET-NEW pack tool (``fixture_tool``, declared in the fixture pack's
    ``tools.json``) is picked up by ``tool_plugins()`` + ``provenance_snapshot()`` through the
    manifest ``tools`` ref ALONE — ZERO engine edits. Subprocess so the fixture pack is active."""
    out = _subproc(
        "from lithrim_bench.harness import plugins as P; "
        "ids={p.id for p in P.tool_plugins()}; "
        "assert 'fixture_tool' in ids, sorted(ids); "
        "snap={p['id'] for p in P.provenance_snapshot()['plugins']}; "
        "assert 'fixture_tool' in snap, sorted(snap); "
        "print('PICKED_UP')",
        pack=_FIXTURE_PACK,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().splitlines()[-1] == "PICKED_UP"


def test_tool1_pack_tool_inherits_pack_tier():
    """TOOL-1: the fixture tool inherits the fixture pack's tier (pro) — the Core/Pro line flows
    from the single ``tier`` field for a pack-contributed tool too."""
    out = _subproc(
        "from lithrim_bench.harness import plugins as P; "
        "t={p.id: p.tier for p in P.tool_plugins()}['fixture_tool']; print(t)",
        pack=_FIXTURE_PACK,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().splitlines()[-1] == "pro"


def test_tool1_pro_tool_skipped_under_denylist():
    """TOOL-1 gate non-vacuity: under ``denylist:fixture_tool`` the fixture PACK still loads
    (permitted) but the pro ``fixture_tool`` is ABSENT from the provenance set — the per-plugin
    skip; the tool plane is tier-gated exactly like contracts/packs. The core ``etlp_jute`` stays."""
    out = _subproc(
        "from lithrim_bench.harness import plugins as P; "
        "ids={p['id'] for p in P.provenance_snapshot()['plugins']}; "
        "assert 'fixture_tool' not in ids, sorted(ids); "
        "assert '_plugin_fixture' in ids and 'etlp_jute' in ids, sorted(ids); "
        "print('SKIPPED')",
        pack=_FIXTURE_PACK,
        license="denylist:fixture_tool",
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().splitlines()[-1] == "SKIPPED"


# ─────────────────────────── A5 — frozen seams + the moat ───────────────────────────


def test_a5_frozen_seam_guards_green():
    """A5 (the moat): the frozen-seam guards stay green (the refactor touched none of the pinned
    seams). Self-contained: pins the two PACK-AGNOSTIC moat seams — the ``judges_dspy`` consensus
    seam (``_apply_consensus`` reader + the finding shape) and the ``compliance_council``
    carve-outs-only guard — both AST/difflib byte-freezes vs ``acc4973`` over CORE files, green with
    no external pack. (The third guard in the healthcare suite, ``assert_clinical_ontology_seam_frozen``,
    verifies the byte-freeze of the external HEALTHCARE clinical ontology — inherently
    healthcare-specific content with no ``_core`` analogue — so it is not part of this self-contained
    variant; the moat/consensus mechanism this A5 pins is fully carried by the two kept guards, which
    stay non-vacuous, i.e. they FAIL if any pinned core seam drifts.)"""
    from ._seam_freeze import (
        assert_compliance_council_carveouts_only,
        assert_judges_dspy_consensus_seam_frozen,
    )

    assert_judges_dspy_consensus_seam_frozen(REPO_ROOT)
    assert_compliance_council_carveouts_only(REPO_ROOT)


def _named_func_source(src: str, name: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(src, node)
    raise AssertionError(f"{name} not found")


def test_a5_moat_apply_consensus_byte_identical_vs_acc4973():
    """A5 (the moat): ``_apply_consensus`` + ``extract_verdict_confidence`` are byte-identical
    (AST-extracted source) between ``acc4973`` and HEAD — the consensus mechanism is untouched.
    Public mode (S-REL-18): the same two sections are hash-pinned (``_FROZEN_SECTION_SHA256``),
    so the attestation stays live without the private history."""
    import tests._seam_freeze as sf

    cur = (REPO_ROOT / _COUNCIL_REL).read_text()
    base = sf._resolve_baseline(REPO_ROOT, _COUNCIL_REL)
    if base is None:
        sf._assert_sections_match_hash_pins(
            "compliance_council.py", sf._council_frozen_sections(cur)
        )
        return
    for name in ("_apply_consensus", "extract_verdict_confidence"):
        assert _named_func_source(base, name) == _named_func_source(cur, name), (
            f"MOAT VIOLATION: {name} changed vs {_SEAM_BASELINE}"
        )


@pytest.mark.parametrize(
    "rel",
    [
        "lithrim_bench/runtime/council/signals.py",
        "lithrim_bench/runtime/council/withstands.py",
    ],
)
def test_a5_withstands_gate_unchanged_vs_parent(rel: str):
    """A5 (D-2 honest pin): the withstands-gate files post-date ``acc4973`` (they did not exist
    there), so the meaningful moat pin for THIS cycle is byte-identity vs the PLUGIN-1 parent.
    S-REL-19: routed through the dual-mode seam — private history → byte-diff of the WORKING
    TREE vs the parent blob (strictly stronger than the old committed-HEAD-only diff); public
    clone → the whole-file sha256 pins (``_FROZEN_FILE_SHA256``), so the attestation stays
    live without the private history."""
    import tests._seam_freeze as sf

    sf.assert_withstands_gate_file_frozen(REPO_ROOT, rel)
