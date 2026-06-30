"""PACKMANIFEST-SEED-AGENTS-FIX: PackManifest must accept the documented `seed_agents` field.

A pack.json may declare `seed_agents` (packs-dropin/README.md; the healthcare pack does) — the
pack-relative agent JSONs the CE seeds into the rail. But `PackManifest` (extra='forbid') lacked
the field, so `validate_pack_manifest()` raised on any pack that declares it, which made
`provenance_snapshot()` throw → the grade pipeline silently degraded to an EMPTY plugin snapshot
(orchestrator.py guards it) and 4 plugin tests failed. Adding the field restores honest provenance.
"""

from __future__ import annotations

from lithrim_bench.harness.plugins import validate_pack_manifest


def test_pack_manifest_accepts_seed_agents():
    raw = {
        "pack_id": "healthcare",
        "version": "1.0.0",
        "tier": "pro",
        "ontology": "ontology.json",
        "flags_ref": "taxonomy_snapshot.json",
        "council_roles": "council_roles",
        "seed_agents": ["agents/healthcare_default.json"],
    }
    m = validate_pack_manifest(raw)
    assert m.seed_agents == ["agents/healthcare_default.json"]


def test_pack_manifest_seed_agents_defaults_empty():
    m = validate_pack_manifest(
        {"pack_id": "p", "ontology": "o.json", "flags_ref": "t.json", "council_roles": "r"}
    )
    assert m.seed_agents == []
