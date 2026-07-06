"""REPRO-1 / R1b — the RECORD reaches the judge: ontology-declared ``grading_context_fields``
fold named case fields (e.g. a patient problem list, an account record) into the grading context
as delimited SOURCE RECORD sections.

The gap this closes: the council's context is transcript + secondary artifacts only — a case's
structured record (``patient_profile`` in the research corpus) never reached the judge prompt,
so record-vs-note failure modes (the subsumption over-block) were not reproducible on-product.
Generic by construction: the FIELD NAMES are user-authored ontology DATA; core reads whatever the
config declares. SIGNATURE-1 hashes the ontology, so editing the list honestly stales prior heads.

$0/offline, stdlib-only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.backends.lithrim_pipeline import _build_context  # noqa: E402
from lithrim_bench.harness.grade import build_request_body  # noqa: E402

_CASE = {
    "case_id": "c1",
    "transcript": "Doctor: what brings you in?",
    "patient_profile": {"conditions": ["Dementia", "Hypertensive disorder"]},
    "tags": ["routine", "follow-up"],
    "artifacts": [{"type": "note", "content": "THE NOTE"}],
}


def test_declared_field_folds_as_a_delimited_record_section():
    ctx = _build_context(_CASE, _CASE["artifacts"], context_fields=("patient_profile",))
    assert ctx.startswith("Doctor: what brings you in?")
    assert "SOURCE RECORD: patient_profile" in ctx
    assert "Dementia" in ctx and "Hypertensive disorder" in ctx


def test_default_is_byte_identical_to_before():
    assert _build_context(_CASE, _CASE["artifacts"]) == _CASE["transcript"]
    assert (
        _build_context(_CASE, _CASE["artifacts"], context_fields=())
        == _CASE["transcript"]
    )


def test_missing_or_empty_declared_field_is_skipped():
    ctx = _build_context(_CASE, _CASE["artifacts"], context_fields=("no_such_field",))
    assert ctx == _CASE["transcript"]


def test_scalar_list_renders_as_bullets_and_order_follows_declaration():
    ctx = _build_context(_CASE, _CASE["artifacts"], context_fields=("tags", "patient_profile"))
    assert "- routine\n- follow-up" in ctx
    assert ctx.index("SOURCE RECORD: tags") < ctx.index("SOURCE RECORD: patient_profile")


def test_live_request_body_reads_the_ontology_declaration():
    body = build_request_body(
        _CASE,
        org_id="o",
        ontology={"flags": [], "grading_context_fields": ["patient_profile"]},
    )
    assert "SOURCE RECORD: patient_profile" in body["context"]
    # undeclared → unchanged
    plain = build_request_body(_CASE, org_id="o", ontology={"flags": []})
    assert plain["context"] == _CASE["transcript"]


def test_local_backend_threads_context_fields_into_the_judge_payload():
    """The declared-fold folds the record into the transcript string AND (REPRO-1 R1b, the
    record-fidelity cut) additionally carries the DECLARED record fields STRUCTURALLY on a dict
    context under ``record`` (field name → value) so the authored stage folds them into the
    judge-visible context. Data-driven: the fold is strictly config-gated — a case with NO
    declared ``grading_context_fields`` is a bare transcript string, byte-identical to before."""
    from lithrim_bench.backends.local_pipeline import LocalPipelineBackend

    # DECLARED: a dict context; the declared fold still folds into the transcript, and the record
    # rides structurally under `record` (keyed by the config-declared field name) for the authored
    # render. No core-hardcoded field name — the backend reads whatever context_fields declares.
    backend = LocalPipelineBackend(context_fields=("patient_profile",))
    request = backend._build_request(_CASE)
    assert isinstance(request.context, dict)
    assert "SOURCE RECORD: patient_profile" in request.context["transcript"]
    assert request.context["record"] == {"patient_profile": _CASE["patient_profile"]}
    # UNDECLARED: even a case carrying a record object is a bare transcript string (config-gated)
    assert LocalPipelineBackend()._build_request(_CASE).context == _CASE["transcript"]
    # a record-less case is likewise a bare transcript string
    record_less = {k: v for k, v in _CASE.items() if k != "patient_profile"}
    declared = LocalPipelineBackend(context_fields=("patient_profile",))
    assert declared._build_request(record_less).context == _CASE["transcript"]


def test_run_eval_threads_the_agents_ontology_declaration(tmp_path, monkeypatch):
    """The wiring: ``run_eval.run(in_process=True)`` reads ``grading_context_fields`` from the
    agent's resolved ontology doc and passes it to the grade seam."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import run_eval as re_mod

    from tests._house_fixture import HOUSE_ONTOLOGY_PATH, house_agent

    ont = json.loads(Path(HOUSE_ONTOLOGY_PATH).read_text())
    ont["grading_context_fields"] = ["patient_profile"]
    ont_path = tmp_path / "ontology.json"
    ont_path.write_text(json.dumps(ont))

    captured: dict = {}

    def _capture(case, **kwargs):
        captured.update(kwargs)
        captured["case"] = case
        raise RuntimeError("captured — stop before any model call")

    monkeypatch.setattr(re_mod, "grade_inprocess", _capture)
    with pytest.raises(RuntimeError, match="captured"):
        re_mod.run(
            house_agent(),
            in_process=True,
            ontology_path=ont_path,
            out_dir=tmp_path / "out",
            collections_db=tmp_path / "coll.sqlite",
        )
    assert tuple(captured.get("context_fields") or ()) == ("patient_profile",)
