"""$0 floor replay over persisted council records: council votes untouched, floor + review recomputed."""

import json
from pathlib import Path

from repro.ragtruth import refloor

SAMPLE = Path("samples/ragtruth")


def test_replay_reproduces_the_committed_queue_states(tmp_path):
    cases = {
        json.loads(ln)["case_id"]: json.loads(ln)
        for ln in (SAMPLE / "cases.jsonl").read_text().splitlines()
        if ln.strip()
    }
    records = {
        cid: {"case_id": cid, "result": json.loads((SAMPLE / f"baseline.{cid}.json").read_text())}
        for cid in cases
    }
    out = refloor.replay(records, cases, out_dir=tmp_path / "o")
    states = sorted(r["composite"]["review"]["state"] for r in out.values())
    assert states == ["ESCALATED"] * 4 + ["FLAGGED"]
    flagged = next(r for r in out.values() if r["composite"]["review"]["state"] == "FLAGGED")
    assert flagged["case_id"] == "ragtruth_10545"
    assert [
        b["evidence"]["missing"] for b in flagged["grounded"]["floor_blocks"] if b["injected"]
    ] == [["50"]]


def test_replay_keeps_council_votes_byte_identical_and_stamps_provenance(tmp_path):
    cases = {
        json.loads(ln)["case_id"]: json.loads(ln)
        for ln in (SAMPLE / "cases.jsonl").read_text().splitlines()
        if ln.strip()
    }
    cid = "ragtruth_9001"
    result = json.loads((SAMPLE / f"baseline.{cid}.json").read_text())
    out = refloor.replay(
        {cid: {"case_id": cid, "result": result}}, {cid: cases[cid]}, out_dir=tmp_path / "o"
    )
    assert out[cid]["result"] == result
    prov = out[cid]["refloor"]
    assert (
        prov["kind"] == "post_hoc_floor_replay"
        and len(prov["tools_py_sha256"]) == 64
        and prov["council_calls"] == 0
    )
    assert (tmp_path / "o" / "runs" / f"{cid}.json").exists() and (
        tmp_path / "o" / "MANIFEST.json"
    ).exists()


def test_replay_with_a_variant_ontology_turns_a_lead_only_block_into_escalation(tmp_path):
    import json as _json

    cases = {
        ln_["case_id"]: ln_
        for ln_ in (
            _json.loads(x) for x in (SAMPLE / "cases.jsonl").read_text().splitlines() if x.strip()
        )
    }
    cid = "ragtruth_2246"  # judges raised codes, floor found nothing to check: ESCALATED via BLOCK under the shipped map
    result = _json.loads((SAMPLE / f"baseline.{cid}.json").read_text())
    base = _json.loads(Path("packs/_core/ontology.json").read_text())
    codes = sorted({f.get("code") for f in result.get("findings", []) if f.get("code")})
    variant = dict(base)
    variant["severity_map"] = {
        **base["severity_map"],
        "lead_codes": codes,
    }  # every raised code demoted to a lead
    vpath = tmp_path / "v.json"
    vpath.write_text(_json.dumps(variant))
    out = refloor.replay(
        {cid: {"case_id": cid, "result": result}},
        {cid: cases[cid]},
        out_dir=tmp_path / "o",
        ontology_path=vpath,
    )
    assert out[cid]["grounded"]["verdict_no_floor"] == "WARN"
    assert out[cid]["composite"]["review"]["state"] == "ESCALATED"
    assert out[cid]["refloor"]["ontology"].endswith("v.json")
