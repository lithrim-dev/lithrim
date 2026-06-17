"""Offline tests for the DSPy JUTE EXTRACTOR + its structural output-invariant (NARR-2).

The extractor is the INGESTION twin of jute_dspy's validator loop: it regenerates the
proven §4.2 per-scene `jute_transform` (SPEC_NARRATIVE_EVAL) and is gated by a hard
structural output-invariant — the apply output must be a JSON ARRAY of `expected_count`
records with ZERO null on the required §4.1 keys. A mis-join (the §4.2 boundary) returns
`null`, not an error → score 0 → rejected.

No network, no LLM: `:3031` is replaced by a Python oracle (FakeExtractorClient) keyed off
a tag in the template string; the DSPy LM is replaced by an injected fake predictor; the
pasted Lenador StoryWorld session is the fixture. The live-convergence test (A6) is
skipif-guarded — a diagnostic, never a default gate.

LOAD-BEARING (A4): the extractor is ingestion-only. It is NEVER a grade-time floor contract —
it must be absent from every floor/contract executor registry (the trust-model separation).
"""

from __future__ import annotations

import json
import os
import types
from pathlib import Path

import pytest

from lithrim_bench.verification import (
    EtlpJuteClient,
    best_of_n_extractor,
    build_extractor_generator,
    extraction_feedback_from,
    make_extraction_metric,
    score_extraction,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "narrative" / "storyworld_session.json"
NARRATIVE_SNAPSHOT = REPO_ROOT / "packs" / "narrative" / "taxonomy_snapshot.json"

# the proven §4.2 per-scene normalizer — preserved verbatim in the spec; the extractor's
# convergence target. (Kept here so the offline oracle can recognize "the golden template".)
PROVEN_TEMPLATE = """$map: $ resource.metadata.enhanced_scenes
$as: e
$body:
  $let: { node: $ str(e.key) }
  $body:
    $let:
      call:
        $reduce: $ resource.metadata.llm_calls
        $as: [acc, c]
        $start: null
        $body: { $if: $ c.scene_node_id = node, $then: $ c, $else: $ acc }
    $body:
      case_id: $ resource.id + "-" + node
      story_id: $ resource.story_id
      mode: $ resource.mode
      language: $ resource.language
      node: $ node
      scene_title: $ e.value.title
      source: $ e.value.source
      model: $ call.model
      finish_reason: $ call.finish_reason
      response: $ e.value.clean_text
"""


@pytest.fixture
def session() -> dict:
    return json.loads(FIXTURE.read_text())


# --------------------------------------------------------------------------- #
# FakeExtractorClient — a Python oracle standing in for the live :3031 engine. The
# template's INTENT is encoded by a tag, so score_extraction can be exercised
# deterministically without JUTE. Two behaviors matter: a GOLDEN per-scene join, and a
# MIS-JOIN (the §4.2 boundary) that returns null/short on the relational join key.
# --------------------------------------------------------------------------- #
def _apply_golden(session: dict) -> list[dict]:
    """Reproduce the §4.2 per-scene output in pure Python (the join the template encodes)."""
    res = session["resource"]
    scenes = res["metadata"]["enhanced_scenes"]
    calls = {c["scene_node_id"]: c for c in res["metadata"]["llm_calls"]}
    out: list[dict] = []
    for node, scene in scenes.items():
        call = calls.get(node) or {}
        out.append(
            {
                "case_id": f"{res['id']}-{node}",
                "story_id": res["story_id"],
                "mode": res["mode"],
                "language": res["language"],
                "node": node,
                "scene_title": scene["title"],
                "source": scene["source"],
                "model": call.get("model"),
                "finish_reason": call.get("finish_reason"),
                "response": scene["clean_text"],
            }
        )
    return out


def _apply_misjoin(session: dict) -> list[dict]:
    """A WRONG key into the source collection: the per-scene lift collapses, so the graded
    content (`response`) AND the identifier (`case_id`) come back null on every record (the
    §4.2 'mis-join returns null' boundary — null on a REQUIRED §4.1 key, not just a passthrough
    field). The structural invariant must reject this."""
    rows = _apply_golden(session)
    for r in rows:
        r["response"] = None
        r["case_id"] = None
        r["model"] = None
        r["finish_reason"] = None
    return rows


class FakeExtractorClient:
    _TAGS = ("noncompile", "misjoin", "short", "golden")

    def __init__(self, session: dict, default: str = "golden") -> None:
        self.session = session
        self.default = default
        self.persisted: list[tuple[str, str]] = []

    def _kind(self, template: str) -> str:
        for tag in self._TAGS:
            if tag in (template or ""):
                return tag
        return self.default

    def _rows(self, kind: str) -> list[dict] | None:
        if kind == "misjoin":
            return _apply_misjoin(self.session)
        if kind == "short":
            return _apply_golden(self.session)[:3]
        return _apply_golden(self.session)

    def test_template(self, template: str, sample_input):
        kind = self._kind(template)
        if kind == "noncompile":
            return {"compiled": False, "output": None, "error": "Jute compile: boom"}
        return {"compiled": True, "output": self._rows(kind), "error": None}

    def apply_mapping(self, mapping_id: int, resource):
        # the live apply returns {result: <array>}; mirror that envelope so score_extraction's
        # result-unwrap is exercised. mapping_id selects the behavior in the live path; here
        # the template tag drives it (the bench is the oracle, not the id).
        return {"result": _apply_golden(self.session)}

    def persist_or_update(self, title: str, yaml_template: str) -> dict:
        self.persisted.append((title, yaml_template))
        return {"id": 555, "title": title, "action": "created"}


# --------------------------------------------------------------------------- #
# A1 — the structural output-invariant rejects a bad extraction
# --------------------------------------------------------------------------- #
def test_extraction_metric_enforces_zero_null_and_count(session):
    client = FakeExtractorClient(session)

    good = score_extraction(client, "golden", session, expected_count=5)
    assert good["accepted"] is True
    assert good["count"] == 5 and good["nulls"] == 0
    assert good["graded"] == 1.0
    assert isinstance(good["cases"], list) and len(good["cases"]) == 5

    # a MIS-JOIN: the wrong join key leaves required keys null -> rejected, score 0
    bad = score_extraction(client, "misjoin", session, expected_count=5)
    assert bad["accepted"] is False
    assert bad["nulls"] > 0 and bad["graded"] == 0.0

    # a SHORT array (len != expected_count) -> rejected
    short = score_extraction(client, "short", session, expected_count=5)
    assert short["accepted"] is False
    assert short["count"] == 3

    # a non-array / non-compiling apply -> rejected, never an exception
    nc = score_extraction(client, "noncompile", session, expected_count=5)
    assert nc["accepted"] is False and nc["count"] == 0


# --------------------------------------------------------------------------- #
# A2 — the proven §4.2 template yields 5 admissible narrative cases
# --------------------------------------------------------------------------- #
def test_proven_template_yields_five_admissible_cases(session):
    client = FakeExtractorClient(session)
    s = score_extraction(client, PROVEN_TEMPLATE, session, expected_count=5)
    assert s["accepted"] is True
    cases = s["cases"]
    assert len(cases) == 5

    # the §4.1 eval-case envelope: each record carries the graded content + an unlabeled,
    # null-injection-recipe shape (ingested data is UNLABELED by construction, HONEST-1).
    for c in cases:
        assert c["case_id"]  # required §4.1 key, non-null
        assert c["artifacts"] and c["artifacts"][0]["content"]  # the graded thing
        assert c["expected_safety_flags"] == []  # unlabeled by construction
        assert c["injection_recipe"] is None
        assert c["context_kind"]  # the input that produced it

    # admissibility under pack=narrative: the (empty) labels are a subset of the tier union.
    tier_union: set[str] = set()
    snap = json.loads(NARRATIVE_SNAPSHOT.read_text())
    for codes in snap["tiers"].values():
        tier_union.update(codes)
    for c in cases:
        assert set(c["expected_safety_flags"]) <= tier_union

    # the content-filtered scene survives extraction (NARR-3's SILENT_DEGRADATION data — the
    # floor that consumes it is a later cycle; NARR-2 only asserts it EXTRACTED).
    cf = [c for c in cases if c.get("finish_reason") == "content_filter"]
    assert len(cf) == 1 and cf[0]["source"] == "baseline"


# --------------------------------------------------------------------------- #
# A4 — trust-model separation: the extractor is NOT a grade-time floor contract
# --------------------------------------------------------------------------- #
def test_extractor_is_not_a_grade_time_floor_contract():
    """The jute_transform extractor is INGESTION-ONLY. It must be absent from every
    grade-time floor/contract executor registry — the moat + the floor-contract set are
    unchanged by this cycle (memory: don't collapse trust models)."""
    from lithrim_bench.harness import grounding

    core_floors = grounding._core_floor_executors()
    floors = grounding.floor_executors()
    suppress = grounding.suppress_executors()
    contracts = grounding._CONTRACT_EXECUTORS

    for registry in (core_floors, floors, suppress, contracts):
        keys = set(registry)
        assert "jute_transform" not in keys
        assert "jute_extractor" not in keys
        assert "JuteExtractor" not in keys

    # the extractor module exports NO VerificationTool/FloorExecutor — it is a generator, not
    # a contract. (A grade-time contract subclasses VerificationTool; the extractor does not.)
    from lithrim_bench.verification import jute_extractor as jx

    assert not hasattr(jx, "JuteExtractorTool")


# --------------------------------------------------------------------------- #
# the refine loop (fake predictor — exercises feedback + convergence, no LM)
# --------------------------------------------------------------------------- #
class FakePredictor:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict] = []

    def __call__(self, **kw):
        self.calls.append(kw)
        out = self.outputs.pop(0) if self.outputs else "golden"
        return types.SimpleNamespace(jute_transform=out)


def test_extractor_refine_loop_feeds_back_and_converges(session):
    pytest.importorskip("dspy")
    client = FakeExtractorClient(session)
    # iter0 a mis-join (null required keys); iter1 a golden template -> converges
    pred = FakePredictor(["a misjoin template", "a golden template"])
    gen = build_extractor_generator(
        client, "DSL", session, expected_count=5, max_iters=3, predictor=pred
    )
    out = gen.forward(extraction_rules="rules", sample_input=session)
    assert out.accepted is True
    assert len(out.history) == 2
    assert out.history[1]["accepted"] is True
    assert pred.calls[0]["prior_feedback"] == ""
    assert pred.calls[1]["prior_feedback"]  # non-empty feedback fed back


def test_extraction_feedback_names_the_failure(session):
    client = FakeExtractorClient(session)
    fb = extraction_feedback_from(score_extraction(client, "misjoin", session, expected_count=5))
    assert "null" in fb.lower() or "NULL" in fb
    short_fb = extraction_feedback_from(
        score_extraction(client, "short", session, expected_count=5)
    )
    assert "5" in short_fb  # names the expected count


def test_make_extraction_metric_graded_and_bootstrap_gate(session):
    client = FakeExtractorClient(session)
    good = make_extraction_metric(client, session, expected_count=5)
    gp = types.SimpleNamespace(jute_transform="golden")
    assert good(None, gp) == 1.0
    assert good(None, gp, trace=[]) is True
    bad = make_extraction_metric(client, session, expected_count=5)
    bp = types.SimpleNamespace(jute_transform="misjoin")
    assert bad(None, bp) < 1.0
    assert bad(None, bp, trace=[]) is False


def test_best_of_n_extractor_returns_first_accepted(session):
    pytest.importorskip("dspy")
    client = FakeExtractorClient(session)
    seq = [["misjoin tmpl"], ["golden tmpl"]]

    def make_gen():
        return build_extractor_generator(
            client, "DSL", session, expected_count=5, max_iters=1,
            predictor=FakePredictor(seq.pop(0)),
        )

    out = best_of_n_extractor(make_gen, "rules", session, n=2)
    assert out.accepted is True


# --------------------------------------------------------------------------- #
# A6 (live, LITHRIM_NARR_LIVE=1) — the extractor converges against :3031. A diagnostic,
# NOT a default gate (live-service dependent; skipped offline).
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(
    not os.getenv("LITHRIM_NARR_LIVE"),
    reason="live-service dependent; set LITHRIM_NARR_LIVE=1 with :3031 up + an LM",
)
def test_live_extractor_converges(session):
    pytest.importorskip("dspy")
    client = EtlpJuteClient()

    def make_gen():
        return build_extractor_generator(client, _live_dsl_excerpt(client), session, expected_count=5)

    out = best_of_n_extractor(make_gen, _NARRATIVE_RULES, session, n=3)
    assert out.accepted is True
    s = score_extraction(client, out.jute_transform, session, expected_count=5)
    assert s["count"] == 5 and s["nulls"] == 0


def _live_dsl_excerpt(client) -> str:
    from lithrim_bench.verification import render_dsl_excerpt

    return render_dsl_excerpt(client.get_dsl_spec(), include_envelope_example=False)


_NARRATIVE_RULES = (
    "Normalize a StoryWorld session JSON into a per-scene array of eval cases. For each entry "
    "in resource.metadata.enhanced_scenes, emit one record joining the matching "
    "resource.metadata.llm_calls row by scene_node_id, with keys: case_id, story_id, mode, "
    "language, node, scene_title, source, model, finish_reason, response (the scene clean_text)."
)


def test_extractor_signature_declares_dsl_excerpt():
    """The extractor signature MUST declare ``dsl_excerpt`` as an InputField so the model
    actually receives the DSL runtime-reality grounding (which builtins work, the 2 YAML rules).
    forward() already passes ``dsl_excerpt=self.dsl_excerpt`` — but if the signature omits it,
    DSPy SILENTLY DROPS it and the model authors JUTE blind to the live :3031 builtin-gap (the
    bug that made live generation never converge). Mirrors the proven jute_dspy.JuteValidatorSignature.
    """
    from lithrim_bench.verification.jute_extractor import _build_extractor_signature

    sig = _build_extractor_signature()
    assert "dsl_excerpt" in sig.input_fields, (
        "dsl_excerpt must be a declared InputField (else DSPy drops the DSL grounding "
        "forward() passes) — see jute_dspy.JuteValidatorSignature"
    )
