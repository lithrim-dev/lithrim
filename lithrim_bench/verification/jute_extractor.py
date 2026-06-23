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


# CRITERIA-AWARE INGEST (gap #4): the extraction target is NOT a fixed envelope — it is THIS
# agent's evaluation criteria. The required in-case fields are derived from the active ontology's
# ``verification_contracts``: each floor's ``*_path`` param names the field it grounds against (e.g.
# ``oracle_path: record.entities``, or ``stated_path: stated_refusals``). Generic —
# driven by the ontology, not any source format.
#
# §4.1 already carries the artifact (response) and the grading context, so a criterion grounding
# against one of THOSE names needs no extra extraction target; everything else a contract names —
# INCLUDING single-segment fields like ``stated_refusals`` — IS a field ingestion must populate.
_ENVELOPE_COVERED = frozenset({"transcript", "note", "response", "context", "artifact", "prompt"})


def required_case_fields(ontology: Any) -> tuple[str, ...]:
    """The in-case fields this agent's criteria ground against, derived from its contracts' params."""
    fields: set[str] = set()
    for c in getattr(ontology, "contracts", ()) or ():
        params = getattr(c, "params", {}) or {}
        for key, value in params.items():
            if (
                key.endswith("_path")
                and isinstance(value, str)
                and value
                and value not in _ENVELOPE_COVERED
            ):
                fields.add(value)
    return tuple(sorted(fields))


def _dig(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _set_path(obj: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


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


# a criteria field is MISSING only when its key is absent or null/empty-string — an empty LIST/DICT
# is a VALID extracted value (e.g. ``noted_refusals=[]`` IS the dissent-erasure the floor grades,
# not a mis-join). Key-presence, not non-emptiness, is the structural invariant for criteria fields.
_MISSING_VALUES = (None, "")


def _missing_criteria(record: Any, required_fields: tuple[str, ...]) -> list[str]:
    """The criteria-required in-case fields (gap #4) a record fails to populate — absent or null at
    the dotted path. Empty list when ``required_fields`` is () — the default §4.1 behavior."""
    if not required_fields:
        return []
    if not isinstance(record, dict):
        return list(required_fields)
    return [p for p in required_fields if _dig(record, p) in _MISSING_VALUES]


# the empty-context sentinels: a `context` string the JUTE transform produced when it FAILED to
# map the input (e.g. a source document). An empty object/array is "present but carries
# nothing" — the artifact would be graded against nothing, the silent-degradation we reject.
_EMPTY_CONTEXT = {"", "{}", "[]", "null", "none"}


def _envelope_incomplete(record: Any) -> list[str]:
    """Envelope-level required fields that survive the transform but carry NOTHING: the graded
    ``content`` and the grading ``context`` (the input the response is graded against — e.g. a
    clinical transcript). A transform whose records have a non-null ``case_id``/``response`` but an
    EMPTY ``context`` (the live 2026-06-17 transcript-drop: every clinical case shipped
    ``context="{}"``) is lossy and must be rejected here, even though ``_null_keys`` passes."""
    if not isinstance(record, dict):
        return ["content", "context"]
    env = _to_envelope(record)
    missing: list[str] = []
    arts = env.get("artifacts") or []
    if not (arts and (arts[0].get("content") or "")):
        missing.append("content")
    ctx = env.get("context")
    if ctx is None or (isinstance(ctx, str) and ctx.strip().lower() in _EMPTY_CONTEXT):
        missing.append("context")
    return missing


def _to_envelope(record: dict, required_fields: tuple[str, ...] = ()) -> dict:
    """Project one raw record into the §4.1 eval-case envelope. Ingested data is UNLABELED by
    construction (customer output is the SUT input, not gold): ``expected_safety_flags: []`` +
    ``injection_recipe: null`` (HONEST-1). ``response`` -> ``artifacts[0].content``.

    DOMAIN-AGNOSTIC context (the 2026-06-17 fix): the grade needs the input the response was
    produced against. An explicit per-record ``context`` (or its ``transcript`` alias — e.g. a
    source transcript) is carried VERBATIM; only when neither is present does the
    envelope fall back to assembling the narrative scene keys (StoryWorld §4.2, back-compat).
    A transform that drops the context entirely is caught by ``score_extraction`` (it never
    silently grades an artifact against ``{}``)."""
    response = record.get("response") or ""
    explicit = record.get("context")
    if explicit in (None, ""):
        explicit = record.get("transcript")
    if explicit not in (None, ""):
        context = explicit if isinstance(explicit, str) else json.dumps(explicit, sort_keys=True)
    else:
        ctx_bits = {
            k: record.get(k)
            for k in (
                "story_id", "mode", "language", "node", "scene_title", "source",
                "prompt", "purpose", "provider",
            )
            if record.get(k) is not None
        }
        context = json.dumps(ctx_bits, sort_keys=True)
    env = {
        "case_id": record.get("case_id"),
        "artifacts": [
            {
                # a transform may name the artifact/context kind for its domain; default unchanged.
                "type": record.get("artifact_type") or "narrative_scene",
                "content": response,
                "metadata": {
                    "model": record.get("model"),
                    "finish_reason": record.get("finish_reason"),
                    "source": record.get("source"),
                },
            }
        ],
        "context": context,
        "context_kind": record.get("context_kind") or "narrative_scene",
        "expected_safety_flags": [],
        "injection_recipe": None,
        # passthrough provenance fields the floor/admissibility may read (not part of §4.1
        # but cheap to carry; the content-filtered scene's finish_reason drives NARR-3).
        "source": record.get("source"),
        "finish_reason": record.get("finish_reason"),
        "model": record.get("model"),
        "node": record.get("node"),
    }
    # CRITERIA-AWARE (gap #4): carry the agent-criteria paths through VERBATIM so the floor's
    # oracle (e.g. record.entities) survives into the gradeable case. Default () =
    # no change (the frozen §4.1 envelope the StoryWorld connector relies on).
    for path in required_fields:
        value = _dig(record, path)
        if value not in (None, ""):
            _set_path(env, path, value)
    return env


# --------------------------------------------------------------------------- #
# the metric (the whole point): the hard structural output-invariant
# --------------------------------------------------------------------------- #
def score_extraction(
    client: Any,
    template: str,
    sample_input: Any,
    *,
    expected_count: int,
    required_fields: tuple[str, ...] = (),
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

    def _incomplete(r: Any) -> list[str]:
        # a record is incomplete if a required §4.1 key is null (mis-join), its ENVELOPE carries
        # no graded content / no grading context (the transcript-drop), OR it fails to populate a
        # criteria-required path (gap #4 — the floor's oracle, e.g. record.entities).
        return _null_keys(r) + _envelope_incomplete(r) + _missing_criteria(r, required_fields)

    null_records = [r for r in array if _incomplete(r)]
    nulls = len(null_records)
    null_keys = sorted({k for r in null_records for k in _incomplete(r)})
    count_ok = count == expected_count
    zero_null = nulls == 0
    accepted = bool(count_ok and zero_null and count > 0)
    # gradient: reward a count match and a high zero-null fraction even before acceptance.
    count_score = 1.0 if count_ok else (min(count, expected_count) / expected_count if expected_count else 0.0)
    null_score = (count - nulls) / count if count else 0.0
    graded = 1.0 if accepted else round(count_score * null_score, 3)
    cases = [_to_envelope(r, required_fields) for r in array] if accepted else []
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
    null_keys = score.get("null_keys") or []
    if "context" in null_keys:
        parts.append(
            "EMPTY GRADING CONTEXT — the transform dropped the input the response is graded "
            "against. Map the source input (e.g. the transcript/prompt/dialogue) into a `context` "
            "field on EVERY record; a response graded against an empty context is meaningless, so "
            "this is rejected even though case_id/response are present."
        )
    if score["nulls"] > 0 and [k for k in null_keys if k not in ("context", "content")]:
        parts.append(
            f"NULL ON REQUIRED KEYS — {score['nulls']} record(s) have null/missing "
            f"{[k for k in null_keys if k not in ('context', 'content')]} (a MIS-JOIN: the "
            "relational $reduce returned null because the join key did not match). Fix the join so "
            "every record's required keys are populated; a mis-join returns null, not an error, so "
            "the metric is the only thing that catches it."
        )
    return " ".join(parts) if parts else "all records present and complete"


def make_extraction_metric(
    client: Any, sample_input: Any, expected_count: int, *, required_fields: tuple[str, ...] = ()
):
    """Build a DSPy-style metric(example, pred, trace=None) -> float|bool over the structural
    invariant (parallels `jute_dspy.make_bench_metric`). With `trace` set (the optimizer
    bootstrap gate) it returns the hard `accepted` bool — only fully invariant-satisfying
    templates become few-shot demos. Otherwise it returns the graded [0,1] gradient."""

    def metric(example: Any, pred: Any, trace: Any = None) -> Any:
        template = strip_fences(getattr(pred, "jute_transform", "") or "")
        if not template.strip():
            return False if trace is not None else 0.0
        s = score_extraction(
            client, template, sample_input, expected_count=expected_count,
            required_fields=required_fields,
        )
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
        (case_id, response) non-null AND a `context` field = the input the response was
        produced/graded against (e.g. the transcript / prompt / source dialogue) — a response
        with no context is graded against nothing and is rejected. If prior_feedback is
        non-empty, FIX exactly what it reports (a MIS-JOIN that left required keys null, or an
        EMPTY GRADING CONTEXT) and return a corrected full template. Output raw YAML only — no
        markdown fences, no commentary.
        """

        dsl_excerpt: str = dspy.InputField(
            desc="the working subset of the JUTE DSL + idioms (RUNTIME REALITY notes — "
            "some documented builtins are UNIMPLEMENTED and fail at apply; trust these over the spec)"
        )
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
    required_fields: tuple[str, ...] = (),
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
            self.required_fields = required_fields

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
                        self.client,
                        template,
                        sample,
                        expected_count=self.expected_count,
                        required_fields=self.required_fields,
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
