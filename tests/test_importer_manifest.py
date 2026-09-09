"""IMPORTER-1: a foreign dataset's vocabulary is a declared, discoverable plugin (kind: importer).

The bridge between RAGTruth's label terms and the pack's taxonomy used to be a private dict in
scripts/ragtruth_cases.py. Now it is packs/_core/importers/ragtruth.json, validated by the
registry, consumed by ingest (inbound) and the scorer/exporter (outbound); a term with no code
fails admissibility; and a SECOND dataset is a second manifest with zero engine edits."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from lithrim_bench.harness import pack as pack_mod
from lithrim_bench.harness.plugins import (
    ImporterManifest,
    PackManifest,
    importer_plugins,
    importer_vocabulary,
)

REPO = Path(__file__).resolve().parents[1]


def test_core_pack_declares_the_ragtruth_vocabulary():
    v = importer_vocabulary("ragtruth", pack="_core")
    assert v.id == "ragtruth_vocabulary" and v.kind == "importer" and v.tier == "core"
    assert v.label_types["Evident Conflict"] == "SOURCE_CONTRADICTION"
    assert v.label_types["Subtle Baseless Info"] == "UNSUPPORTED_ASSERTION"
    assert v.terms_for("SOURCE_CONTRADICTION") == ["Evident Conflict", "Subtle Conflict"]
    assert "ragtruth" in v.verdict_rule and "lithrim" in v.verdict_rule
    assert "subtlety" in v.metadata_fields
    # every mapped code exists in the pack's taxonomy (labels stay true by construction)
    snap = json.loads((REPO / "packs/_core/taxonomy_snapshot.json").read_text())
    known = {c for tier in snap["tiers"].values() for c in tier}
    assert set(v.label_types.values()) <= known


def test_an_unmapped_term_fails_admissibility_never_a_silent_drop():
    v = importer_vocabulary("ragtruth", pack="_core")
    with pytest.raises(LookupError, match="no taxonomy code"):
        v.code_for("Made Up Type")
    with pytest.raises(LookupError, match="no kind:importer manifest"):
        importer_vocabulary("no_such_dataset", pack="_core")


def test_manifest_is_a_real_contract():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ImporterManifest.model_validate({"id": "x", "dataset": "d", "label_types": {}, "typo": 1})
    assert PackManifest.model_validate(
        json.loads((REPO / "packs/_core/pack.json").read_text())
    ).importers == ["importers/ragtruth.json"]


def test_manifest_declares_the_case_paths_and_the_engine_reads_through_them():
    """ENGINE-CLEAN-1: the engine never names a dataset. Where a case keeps its source id and
    its gold spans is declared by the importer manifest (dotted paths); a case with no manifest
    behind it still works through the neutral top-level ``source_id`` / ``gold_spans``."""
    from lithrim_bench.harness.plugins import case_gold_spans, case_source_id

    v = importer_vocabulary("ragtruth", pack="_core")
    assert v.source_id_path == "ragtruth.source_id" and v.gold_spans_path == "ragtruth.labels"
    shaped = {"case_id": "c", "ragtruth": {"source_id": "s7", "labels": [{"start": 0, "end": 1}]}}
    assert case_source_id(shaped, pack="_core") == "s7"
    assert case_gold_spans(shaped, pack="_core") == [{"start": 0, "end": 1}]
    bare = {"case_id": "c", "source_id": "n1", "gold_spans": [{"text": "x"}]}
    assert case_source_id(bare, pack="_core") == "n1"
    assert case_gold_spans(bare, pack="_core") == [{"text": "x"}]
    assert case_source_id({"case_id": "c"}, pack="_core") is None
    assert case_gold_spans({"case_id": "c"}, pack="_core") is None
    assert case_gold_spans({"case_id": "c", "ragtruth": {"labels": []}}, pack="_core") is None
    # a manifest without the paths is valid (they are optional) and contributes nothing
    m = ImporterManifest.model_validate({"id": "x", "dataset": "d", "label_types": {}})
    assert m.source_id_path is None and m.gold_spans_path is None


def test_open_closed_a_second_dataset_is_a_second_manifest(tmp_path, monkeypatch):
    """Zero engine edits: copy the core pack, add a manifest for another dataset, point
    LITHRIM_BENCH_PACKS_DIR at it, and the registry discovers both."""
    dst = tmp_path / "otherpack"
    shutil.copytree(REPO / "packs" / "_core", dst)
    pj = json.loads((dst / "pack.json").read_text())
    pj["pack_id"] = "otherpack"
    pj["importers"] = ["importers/ragtruth.json", "importers/halueval.json"]
    (dst / "pack.json").write_text(json.dumps(pj))
    (dst / "importers" / "halueval.json").write_text(
        json.dumps(
            {
                "id": "halueval_vocabulary",
                "dataset": "halueval",
                "label_types": {"hallucinated": "UNSUPPORTED_ASSERTION"},
                "verdict_rule": {"halueval": "binary", "lithrim": "any Tier-1 finding => BLOCK"},
            }
        )
    )
    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(tmp_path))
    pack_mod._pack_root.cache_clear()
    pack_mod._manifest.cache_clear()
    pack_mod._load_pack_importers.cache_clear()
    try:
        ids = {m.id: m for m in importer_plugins("otherpack")}
        assert set(ids) == {"ragtruth_vocabulary", "halueval_vocabulary"}
        assert ids["halueval_vocabulary"].tier == "core"  # inherits the pack tier
        assert (
            importer_vocabulary("halueval", pack="otherpack").code_for("hallucinated")
            == "UNSUPPORTED_ASSERTION"
        )
    finally:
        pack_mod._pack_root.cache_clear()
        pack_mod._manifest.cache_clear()
        pack_mod._load_pack_importers.cache_clear()
