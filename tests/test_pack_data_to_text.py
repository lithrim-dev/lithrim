"""packs/data_to_text: a neutral, non-clinical pack for text written from a structured record.
Own ontology (RAGTruth-aligned codes), own prompts, core grounding inherited, no engine edits."""

import json
from pathlib import Path

from lithrim_bench.harness import pack as pack_mod
from lithrim_bench.harness.ontology import load_ontology

PACK = "data_to_text"
ROOT = Path("packs") / PACK
GRADEABLE = {"SOURCE_CONTRADICTION", "UNSUPPORTED_ASSERTION", "NULL_AS_NEGATION"}
REFERENCE = {"MISSING_CONTEXT", "FABRICATED_CLAIM", "STYLE_VIOLATION", "INTERNAL_INCONSISTENCY"}
ROLES = ["risk_judge", "policy_judge", "faithfulness_judge"]


def derive_snapshot(ontology: dict, judges: list[str]) -> dict:
    """The deterministic derivation the committed snapshot must equal (never hand-edited)."""
    flags = [f for f in ontology["flags"] if f.get("gradeable")]
    tiers = {"TIER_1_NEVER_EVENTS": [], "TIER_2_HIGH_RISK": [], "TIER_3_MEDIUM": []}
    key = {"TIER_1": "TIER_1_NEVER_EVENTS", "TIER_2": "TIER_2_HIGH_RISK", "TIER_3": "TIER_3_MEDIUM"}
    for f in flags:
        tiers[key[f["tier"]]].append(f["flag"])
    lenses = {r: [f["flag"] for f in flags if r in f["owner_roles"]] for r in judges}
    return {
        "snapshot_metadata": ontology["_provenance"]["snapshot_metadata"],
        "tiers": tiers,
        "tier1_owners": {f["flag"]: list(f["owner_roles"]) for f in flags if f["tier"] == "TIER_1"},
        "production_judges": list(judges),
        "lenses": lenses,
        "declared_but_not_running": [],
    }


def test_pack_discovers_and_validates_as_core():
    root = pack_mod.pack_root(PACK)
    manifest = json.loads((root / "pack.json").read_text())
    assert (
        manifest["pack_id"] == PACK and manifest["tier"] == "core" and manifest["judges"] == ROLES
    )
    assert (root / manifest["ontology"]).exists() and (root / manifest["flags_ref"]).exists()
    assert {p.name for p in (root / manifest["council_roles"]).glob("*.txt")} == {
        f"{r}.txt" for r in ROLES
    }


def test_gradeable_flags_have_running_owners_and_lenses_carry_nothing_else():
    onto = load_ontology(ROOT / "ontology.json")
    assert {f.flag for f in onto.gradeable_flags()} == GRADEABLE
    for code in REFERENCE:
        assert onto.is_reference(code), code
    lenses = pack_mod.pack_lenses(PACK)
    owners = pack_mod.pack_tier1_owners(PACK)
    assert set(pack_mod.pack_production_judges(PACK)) == set(ROLES)
    assert set(owners) == GRADEABLE and all(set(v) <= set(ROLES) for v in owners.values())
    assert set().union(*lenses.values()) == GRADEABLE
    assert not any(set(v) & REFERENCE for v in lenses.values())
    assert all(len(v) == 1 for v in lenses.values())  # one code per judge, by design


def test_snapshot_equals_the_deterministic_derivation():
    onto = json.loads((ROOT / "ontology.json").read_text())
    manifest = json.loads((ROOT / "pack.json").read_text())
    assert json.loads((ROOT / "taxonomy_snapshot.json").read_text()) == derive_snapshot(
        onto, manifest["judges"]
    )


def test_prompts_never_name_a_reference_code_and_name_exactly_their_own():
    lenses = pack_mod.pack_lenses(PACK)
    for role in ROLES:
        text = (ROOT / "council_roles" / f"{role}.txt").read_text()
        for code in REFERENCE:
            assert code not in text, (role, code)
        for code in lenses[role]:
            assert code in text
        assert "null" in text.lower() and "unknown" in text.lower()


def test_contracts_inherit_core_grounding_only():
    onto = json.loads((ROOT / "ontology.json").read_text())
    types = {c["contract_type"] for c in onto["verification_contracts"]}
    assert types <= {"value_grounding", "source_grounding", "null_negation"}
    assert any(
        c["contract_type"] == "value_grounding"
        and c["params"]["inject_flag_code"] == "SOURCE_CONTRADICTION"
        for c in onto["verification_contracts"]
    )


def test_pack_passes_the_ce_data_surface_sweep():
    from tests.test_pack_dist import _NEEDLES

    for p in ROOT.rglob("*"):
        if p.is_file():
            low = p.read_text(errors="ignore").lower()
            hits = [n for n in _NEEDLES if n in low]
            assert not hits, (p, hits)


def test_stray_reference_code_never_drives_the_verdict(monkeypatch):
    from lithrim_bench.harness.grounding import ground

    monkeypatch.setenv(
        "LITHRIM_BENCH_PACK", PACK
    )  # ground() resolves pack executors via the active pack

    onto = load_ontology(ROOT / "ontology.json")
    case = {
        "case_id": "x",
        "source_kind": "record",
        "transcript": '{"name": "Cafe", "business_stars": 4.5}',
        "artifacts": [{"content": "Cafe has a 4.5-star rating."}],
    }
    result = {
        "verdict": "WARN",
        "findings": [{"code": "MISSING_CONTEXT", "severity": "HIGH", "evidence": "omits hours"}],
        "semantic": {"judge_votes": []},
    }
    g = ground(result, case, ontology=onto)
    assert [f["code"] for f in g.skipped_non_gradeable] == ["MISSING_CONTEXT"]
    assert g.verdict_no_floor == "PASS" and g.verdict == "PASS"
