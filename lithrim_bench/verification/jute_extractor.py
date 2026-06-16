"""JuteExtractor — the INGESTION twin of the jute_dspy validator loop (NARR-2).

This parallels `jute_dspy.py` (it does NOT import-and-mutate it): the same generate ->
live-gate -> refine loop, owned by the bench, but the task is the OTHER JUTE face —
TRANSFORM arbitrary domain JSON into a list of admissible eval cases (the §4.2
`jute_transform`), not VALIDATE a resource. The loop's oracle here is a hard STRUCTURAL
OUTPUT-INVARIANT: the apply output must be a JSON ARRAY of `expected_count` records with
ZERO null on the required §4.1 keys (the §4.2 boundary — a mis-join returns `null`, not an
error, so the metric is the only thing that catches it). This is the SAME burden a
verdict-feeding validator carries (SPEC_GROUNDING_TOOL_LAYER.md), gated at generation time
(test_template) AND at apply time.

TRUST-MODEL SEPARATION (load-bearing): this module is INGESTION-ONLY. It is NEVER registered
in any grade-time floor/contract executor registry (`harness/grounding._CONTRACT_EXECUTORS`,
`_core_floor_executors`, `floor_executors`, `suppress_executors`). It exports a GENERATOR,
not a VerificationTool — ingestion and verdict-grounding are different trust models
(memory `jute-generated-contracts-unification`: "don't collapse trust models").

Reuses `strip_fences` + `render_dsl_excerpt` from jute_dspy (the runtime/builtin-gap notes
ride render_dsl_excerpt) and `EtlpJuteClient.test_template`/`apply_mapping` from etlp_client.
"""

from __future__ import annotations

import json
from typing import Any

from .jute_dspy import strip_fences

# the §4.1 eval-case envelope keys the extractor output MUST populate non-null. `case_id`
# identifies the record; the graded content arrives as `response` (per-scene clean_text) and
# is lifted into `artifacts[0].content`. A null on either = a mis-join the invariant rejects.
_REQUIRED_KEYS = ("case_id", "response")


def _coerce_array(applied: Any) -> list | None:
    """Lift the per-scene array out of an apply/test-template response. The live apply returns
    ``{result: <array>}``; test-template returns ``{compiled, output, error}`` with ``output``
    the array. A non-array (a mis-join collapsing to a scalar/null, or a non-compile) returns
    ``None`` — the invariant then scores it 0 (NEVER raises; the §4.2 boundary)."""
    if applied is None:
        return None
    if isinstance(applied, list):
        return applied
    if isinstance(applied, dict):
        if "result" in applied:
            return _coerce_array(applied.get("result"))
        if "output" in applied:
            # test-template shape: honor `compiled`, else the output array
            if applied.get("compiled") is False:
                return None
            return _coerce_array(applied.get("output"))
    return None


def _null_keys(record: Any) -> list[str]:
    """The required §4.1 keys that are missing/null on one record (the mis-join symptom)."""
    if not isinstance(record, dict):
        return list(_REQUIRED_KEYS)
    return [k for k in _REQUIRED_KEYS if record.get(k) in (None, "")]


def _to_envelope(record: dict) -> dict:
    """Project one raw per-scene record into the §4.1 eval-case envelope. Ingested data is
    UNLABELED by construction (customer output is the SUT input, not gold): ``expected_safety_
    flags: []`` + ``injection_recipe: null`` (HONEST-1). ``response`` -> ``artifacts[0].content``;
    the scene metadata rides ``context`` so the grade has the prompt-shape that produced it."""
    response = record.get("response") or ""
    ctx_bits = {
        k: record.get(k)
        for k in ("story_id", "mode", "language", "node", "scene_title", "source")
        if record.get(k) is not None
    }
    return {
        "case_id": record.get("case_id"),
        "artifacts": [
            {
                "type": "narrative_scene",
                "content": response,
                "metadata": {
                    "model": record.get("model"),
                    "finish_reason": record.get("finish_reason"),
                    "source": record.get("source"),
                },
            }
        ],
        "context": json.dumps(ctx_bits, sort_keys=True),
        "context_kind": "narrative_scene",
        "expected_safety_flags": [],
        "injection_recipe": None,
        # passthrough provenance fields the floor/admissibility may read (not part of §4.1
        # but cheap to carry; the content-filtered scene's finish_reason drives NARR-3).
        "source": record.get("source"),
        "finish_reason": record.get("finish_reason"),
        "model": record.get("model"),
        "node": record.get("node"),
    }


# --------------------------------------------------------------------------- #
# the metric (the whole point): the hard structural output-invariant
# --------------------------------------------------------------------------- #
def score_extraction(
    client: Any, template: str, sample_input: Any, *, expected_count: int
) -> dict:
    """Score a candidate `jute_transform` against the structural output-invariant.

    Applies the template to `sample_input` via the live in-memory `test_template`, then
    enforces: the output is a JSON ARRAY, `len == expected_count`, and ZERO null on the
    required §4.1 keys of EVERY record. `accepted` iff all three hold. `graded` is the
    fraction of the burden met (count-match * zero-null-fraction) — the gradient the
    optimizer climbs. A mis-join collapses to `null`/scalar -> `count: 0`, `graded: 0.0`
    (NEVER raises). On accept, `cases` is the §4.1-enveloped list ready to PIN + upsert.
    """
    tt = client.test_template(template, sample_input)
    array = _coerce_array(tt)
    if array is None:
        error = tt.get("error") if isinstance(tt, dict) else "no array output"
        return {
            "accepted": False,
            "graded": 0.0,
            "count": 0,
            "expected_count": expected_count,
            "nulls": expected_count or 1,
            "null_keys": list(_REQUIRED_KEYS),
            "cases": [],
            "error": error,
        }
    count = len(array)
    null_records = [r for r in array if _null_keys(r)]
    nulls = len(null_records)
    null_keys = sorted({k for r in null_records for k in _null_keys(r)})
    count_ok = count == expected_count
    zero_null = nulls == 0
    accepted = bool(count_ok and zero_null and count > 0)
    # gradient: reward a count match and a high zero-null fraction even before acceptance.
    count_score = 1.0 if count_ok else (min(count, expected_count) / expected_count if expected_count else 0.0)
    null_score = (count - nulls) / count if count else 0.0
    graded = 1.0 if accepted else round(count_score * null_score, 3)
    cases = [_to_envelope(r) for r in array] if accepted else []
    return {
        "accepted": accepted,
        "graded": graded,
        "count": count,
        "expected_count": expected_count,
        "nulls": nulls,
        "null_keys": null_keys,
        "cases": cases,
        "error": None,
    }


def extraction_feedback_from(score: dict) -> str:
    """Turn an extraction score into refine-loop feedback the generator can act on (parallels
    `jute_dspy.feedback_from`). Names the structural failure precisely so the next attempt
    fixes the JOIN, not the YAML at random."""
    if score.get("error"):
        return (
            f"DID NOT COMPILE / produced no array: {str(score['error'])[:280]}. Return a "
            "corrected full template. Reminders: every $ expression must be on ONE line; the "
            "object-map key is a keyword (use str(e.key) to strip the ':'); the cross-array join "
            "uses $reduce ($start null, $if c.scene_node_id = node) — there is NO $filter."
        )
    parts: list[str] = []
    if score["count"] != score["expected_count"]:
        parts.append(
            f"WRONG ROW COUNT — produced {score['count']} records but expected "
            f"{score['expected_count']}. Iterate over EVERY entry of the source collection "
            "(one record per scene), do not drop or duplicate."
        )
    if score["nulls"] > 0:
        parts.append(
            f"NULL ON REQUIRED KEYS — {score['nulls']} record(s) have null/missing "
            f"{score['null_keys']} (a MIS-JOIN: the relational $reduce returned null because the "
            "join key did not match). Fix the join so every record's required keys are populated; "
            "a mis-join returns null, not an error, so the metric is the only thing that catches it."
        )
    return " ".join(parts) if parts else "all records present and complete"


def make_extraction_metric(client: Any, sample_input: Any, expected_count: int):
    """Build a DSPy-style metric(example, pred, trace=None) -> float|bool over the structural
    invariant (parallels `jute_dspy.make_bench_metric`). With `trace` set (the optimizer
    bootstrap gate) it returns the hard `accepted` bool — only fully invariant-satisfying
    templates become few-shot demos. Otherwise it returns the graded [0,1] gradient."""

    def metric(example: Any, pred: Any, trace: Any = None) -> Any:
        template = strip_fences(getattr(pred, "jute_transform", "") or "")
        if not template.strip():
            return False if trace is not None else 0.0
        s = score_extraction(client, template, sample_input, expected_count=expected_count)
        if trace is not None:
            return bool(s["accepted"])
        return 1.0 if s["accepted"] else s["graded"]

    return metric


# --------------------------------------------------------------------------- #
# the DSPy program: the extractor refine loop owned by the bench
# --------------------------------------------------------------------------- #
def _build_extractor_signature():
    import dspy

    class JuteExtractorSignature(dspy.Signature):
        """Author a JUTE `jute_transform` (raw YAML) that normalizes a domain JSON dump into
        a JSON ARRAY of eval-case records.

        Ground STRICTLY in the DSL excerpt's RUNTIME REALITY notes — some documented builtins
        are unimplemented and will fail. Emit ONE record per entry of the source collection,
        joining any related collection by key. Each record MUST populate the required keys
        (case_id, response) non-null. If prior_feedback is non-empty, FIX exactly what it
        reports (esp. a MIS-JOIN that left required keys null) and return a corrected full
        template. Output raw YAML only — no markdown fences, no commentary.
        """

        extraction_rules: str = dspy.InputField(desc="what a 'case' is + which keys to emit")
        sample_input: str = dspy.InputField(desc="a sample of the domain JSON to normalize")
        prior_template: str = dspy.InputField(desc="the previous attempt, or '' on the first try")
        prior_feedback: str = dspy.InputField(
            desc="structural feedback on the prior attempt (count/null/compile), or ''"
        )
        jute_transform: str = dspy.OutputField(desc="the JUTE transform as raw YAML")

    return JuteExtractorSignature


def build_extractor_generator(
    client: Any,
    dsl_excerpt: str,
    sample_input: Any,
    *,
    expected_count: int,
    max_iters: int = 3,
    predictor: Any = None,
    seed_template: str = "",
    seed_feedback: str = "",
):
    """Construct a JuteExtractorGenerator (parallels `jute_dspy.build_generator`). `predictor`
    is injectable for offline tests (a callable returning an object with `.jute_transform`);
    defaults to a live `dspy.ChainOfThought` over the signature. `seed_template`/`seed_feedback`
    seed iteration 0 (e.g. with the proven §4.2 template) so the loop makes a MINIMAL edit
    rather than re-deriving from scratch."""
    import dspy

    class JuteExtractorGenerator(dspy.Module):
        def __init__(self) -> None:
            super().__init__()
            self.gen = (
                predictor
                if predictor is not None
                else dspy.ChainOfThought(_build_extractor_signature())
            )
            self.client = client
            self.dsl_excerpt = dsl_excerpt
            self.sample_input = sample_input
            self.expected_count = expected_count
            self.max_iters = max_iters
            self.seed_template = seed_template
            self.seed_feedback = seed_feedback

        def forward(self, extraction_rules: str, sample_input: Any = None) -> Any:
            sample = sample_input if sample_input is not None else self.sample_input
            sample = json.loads(sample) if isinstance(sample, str) else sample
            sample_json = json.dumps(sample)
            prior_template, prior_feedback = self.seed_template, self.seed_feedback
            history: list[dict] = []
            best: str | None = None
            best_score: dict | None = None
            for it in range(self.max_iters):
                pred = self.gen(
                    dsl_excerpt=self.dsl_excerpt,
                    extraction_rules=extraction_rules,
                    sample_input=sample_json,
                    prior_template=prior_template,
                    prior_feedback=prior_feedback,
                )
                template = strip_fences(getattr(pred, "jute_transform", "") or "")
                s = (
                    score_extraction(
                        self.client, template, sample, expected_count=self.expected_count
                    )
                    if template.strip()
                    else {
                        "accepted": False,
                        "graded": 0.0,
                        "count": 0,
                        "expected_count": self.expected_count,
                        "nulls": self.expected_count,
                        "null_keys": list(_REQUIRED_KEYS),
                        "cases": [],
                        "error": "empty template",
                    }
                )
                history.append(
                    {
                        "iter": it,
                        "accepted": s["accepted"],
                        "graded": round(s["graded"], 3),
                        "count": s["count"],
                        "nulls": s["nulls"],
                    }
                )
                if best_score is None or s["graded"] > best_score["graded"]:
                    best, best_score = template, s
                if s["accepted"]:
                    break
                prior_template = template
                prior_feedback = extraction_feedback_from(s)
            return dspy.Prediction(
                jute_transform=best or "",
                accepted=bool(best_score and best_score["accepted"]),
                score=best_score,
                cases=(best_score or {}).get("cases", []),
                history=history,
            )

    return JuteExtractorGenerator()


def best_of_n_extractor(make_gen, extraction_rules: str, sample_input: Any, *, n: int = 3) -> Any:
    """Run the extractor refine-loop up to N independent times; return the first invariant-
    accepted prediction, else the highest-graded one (parallels `jute_dspy.best_of_n`).
    `make_gen` is a 0-arg factory so each attempt is a fresh module instance."""
    best = None
    for _ in range(n):
        pred = make_gen().forward(extraction_rules=extraction_rules, sample_input=sample_input)
        if getattr(pred, "accepted", False):
            return pred
        graded = (getattr(pred, "score", None) or {}).get("graded", 0.0)
        if best is None or graded > (getattr(best, "score", None) or {}).get("graded", 0.0):
            best = pred
    return best
