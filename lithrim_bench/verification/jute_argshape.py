"""JuteArgShape — the AUTHORING-TIME twin of the CRITERION-JUTE-1a grade-time wire.

This SIBLINGS `jute_extractor.py` (it does NOT import-and-mutate it): the same generate ->
live-gate -> refine loop, owned by the bench, but the task is the THIRD JUTE face —
shape the `arguments` object a tool CALL expects, drawn from a sample eval case + finding
(the `arguments_jute` a flag's `verification_contract` pins), not VALIDATE a resource and
not EXTRACT an array of cases. The loop's oracle here is a STRUCTURAL OUTPUT-INVARIANT keyed
to the tool call's `inputSchema`: the apply output must be a SINGLE JSON OBJECT carrying every
`required` key of the schema, non-null and correctly typed — a mis-map returns `null`/a scalar,
not an error, so the metric is the only thing that catches it.

ENVELOPE (load-bearing — MUST stay byte-identical to what 1a applies at grade time): the 1a
wire (`grounding.McpCallGrounding._shape_arguments`) applies the pinned transform via
`EtlpJuteClient.test_template(jute, {"case": case, "finding": finding})`. `test_template` wraps
its `sample_input` as `{resource: sample_input}` before applying (etlp_client.py:107), so inside
the JUTE the root is `resource` and the transform reads `resource.case.*` / `resource.finding.*`.
The generator's `sample_input` is therefore that same `{"case": ..., "finding": ...}` envelope —
the gated transform is the exact object 1a pins and re-applies.

TRUST-MODEL SEPARATION (load-bearing): this module is AUTHORING-ONLY. It is NEVER registered in
any grade-time floor/contract executor registry — it exports a GENERATOR + a SCORER, not a
VerificationContract. The pinned OUTPUT (an `arguments_jute` template + its sha256) is what rides
the flag's contract; the grade-time consumer is 1a. Generation and verdict-grounding are different
trust models (memory `jute-generated-contracts-unification`: "don't collapse trust models").

Reuses `strip_fences` from jute_dspy and `EtlpJuteClient.test_template` from etlp_client. Networkless
to test: `score_argshape` takes a plain `input_schema` dict the CALLER passes (the 1d BFF endpoint
reads it live via `McpStdioClient.list_tools()` and hands it in); this module never touches the wire.
"""

from __future__ import annotations

import json
from typing import Any

from .jute_dspy import strip_fences

# the JSON-primitive expected for each JSON-Schema `type`. `bool` is a subclass of `int` in Python,
# so an `integer`/`number` check must EXCLUDE bool explicitly (a `True` is not a valid concept id).
_SCHEMA_PY_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


def required_keys_of(input_schema: Any) -> tuple[str, ...]:
    """The `required` keys of a JSON-Schema object — the arguments the tool call MUST receive."""
    if not isinstance(input_schema, dict):
        return ()
    req = input_schema.get("required") or ()
    return tuple(k for k in req if isinstance(k, str))


def schema_type_of(input_schema: Any, key: str) -> str | None:
    """The declared JSON-Schema `type` of one property, or None if the property/type is absent."""
    if not isinstance(input_schema, dict):
        return None
    prop = (input_schema.get("properties") or {}).get(key)
    if not isinstance(prop, dict):
        return None
    t = prop.get("type")
    return t if isinstance(t, str) else None


def _type_ok(value: Any, schema_type: str | None) -> bool:
    """Whether `value` satisfies the JSON-Schema primitive `schema_type`. An unknown/absent type is
    permissive (presence-non-null is the only burden). `boolean` matches only bool; `integer`/`number`
    EXCLUDE bool (a bool is not a numeric argument, even though Python `bool` is an `int` subclass)."""
    if schema_type is None:
        return True
    expected = _SCHEMA_PY_TYPES.get(schema_type)
    if expected is None:
        return True
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type in ("integer", "number"):
        return isinstance(value, expected) and not isinstance(value, bool)
    return isinstance(value, expected)


def _coerce_object(applied: Any) -> dict | None:
    """Lift the arguments OBJECT out of a test-template response. `test_template` returns
    ``{compiled, output, error}`` with ``output`` the shaped object. A non-object (a mis-map
    collapsing to a scalar/array/null, or a non-compile) returns ``None`` — the invariant then
    scores it 0 (NEVER raises)."""
    if not isinstance(applied, dict):
        return None
    if applied.get("compiled") is False:
        return None
    output = applied.get("output")
    return output if isinstance(output, dict) else None


# --------------------------------------------------------------------------- #
# the metric (the whole point): the hard output-invariant, keyed to inputSchema
# --------------------------------------------------------------------------- #
def score_argshape(
    client: Any,
    template: str,
    sample_input: Any,
    *,
    input_schema: dict,
) -> dict:
    """Score a candidate `arguments_jute` template against the tool call's inputSchema.

    Applies the template to `sample_input` (the `{case, finding}` envelope, wrapped as
    `{resource: ...}` by test_template) via the live in-memory `test_template`, then enforces: the
    output is a SINGLE JSON OBJECT and every `required` key of `input_schema` is present, non-null,
    and of the correct JSON-primitive type. `accepted` iff all hold. `graded` is the fraction of the
    required keys satisfied (present-non-null-correctly-typed) — the gradient the optimizer climbs.
    A mis-map collapses to `null`/scalar/array -> `graded: 0.0` (NEVER raises). On accept,
    `arguments` is the shaped object ready to PIN; else `{}`.
    """
    required = required_keys_of(input_schema)
    tt = client.test_template(template, sample_input)
    output = _coerce_object(tt)
    if output is None:
        error = tt.get("error") if isinstance(tt, dict) else "no object output"
        return {
            "accepted": False,
            "graded": 0.0,
            "arguments": {},
            "missing_keys": list(required),
            "type_errors": [],
            "error": error,
        }

    missing_keys: list[str] = []
    type_errors: list[str] = []
    for key in required:
        if output.get(key) is None:
            missing_keys.append(key)
            continue
        if not _type_ok(output.get(key), schema_type_of(input_schema, key)):
            type_errors.append(key)

    total = len(required)
    bad = len(missing_keys) + len(type_errors)
    graded = 1.0 if total == 0 else round((total - bad) / total, 3)
    accepted = bad == 0 and isinstance(output, dict)
    return {
        "accepted": accepted,
        "graded": 1.0 if accepted else graded,
        "arguments": output if accepted else {},
        "missing_keys": missing_keys,
        "type_errors": type_errors,
        "error": None,
    }


def argshape_feedback_from(score: dict) -> str:
    """Turn an argshape score into refine-loop feedback the generator can act on (parallels
    `jute_extractor.extraction_feedback_from`). Names the exact failure — a missing required key, a
    wrong-typed key, or a non-compile — so the next attempt fixes the MAP, not the YAML at random."""
    if score.get("error"):
        return (
            f"DID NOT COMPILE / produced no arguments object: {str(score['error'])[:280]}. Return a "
            "corrected full template that emits ONE JSON object. Reminders: every $ expression must be "
            "on ONE line; the object-map key is a keyword (use str(e.key) to strip the ':'); the output "
            "must be a single object, NOT an array."
        )
    parts: list[str] = []
    missing = score.get("missing_keys") or []
    if missing:
        parts.append(
            f"MISSING REQUIRED KEYS — the output object is missing/null on {missing}. The tool call's "
            "inputSchema REQUIRES every one of these keys present + non-null. Map each from the sample "
            "envelope (resource.case.* / resource.finding.*); a mis-map returns null, not an error, so "
            "the metric is the only thing that catches it."
        )
    type_errors = score.get("type_errors") or []
    if type_errors:
        parts.append(
            f"WRONG TYPE ON REQUIRED KEYS — {type_errors} are present but the wrong JSON type for the "
            "inputSchema (e.g. a string where `integer` is required, or a bool where a number is "
            "required — a bool is NOT an integer). Coerce each to the schema's declared type "
            "($toInt / $toString) so the type matches exactly."
        )
    return " ".join(parts) if parts else "all required arguments present and correctly typed"


def make_argshape_metric(client: Any, sample_input: Any, *, input_schema: dict):
    """Build a DSPy-style metric(example, pred, trace=None) -> float|bool over the argshape
    invariant (parallels `jute_extractor.make_extraction_metric`). With `trace` set (the optimizer
    bootstrap gate) it returns the hard `accepted` bool — only fully invariant-satisfying templates
    become few-shot demos. Otherwise it returns the graded [0,1] gradient."""

    def metric(example: Any, pred: Any, trace: Any = None) -> Any:
        template = strip_fences(getattr(pred, "jute_transform", "") or "")
        if not template.strip():
            return False if trace is not None else 0.0
        s = score_argshape(client, template, sample_input, input_schema=input_schema)
        if trace is not None:
            return bool(s["accepted"])
        return 1.0 if s["accepted"] else s["graded"]

    return metric


# --------------------------------------------------------------------------- #
# the DSPy program: the argshape refine loop owned by the bench
# --------------------------------------------------------------------------- #
def _build_argshape_signature():
    import dspy

    class JuteArgShapeSignature(dspy.Signature):
        """Author a JUTE `jute_transform` (raw YAML) that shapes the `arguments` object a tool CALL
        expects, drawn from a sample eval case + finding.

        Emit ONE JSON OBJECT that EXACTLY matches `input_schema`: every `required` key present,
        non-null, and of the schema's declared type. Read the values from the sample envelope under
        `resource.case.*` / `resource.finding.*` (test-template wraps the envelope as `{resource: ...}`
        before applying). Coerce to the schema's type ($toInt / $toString) so the type matches exactly
        — a string where `integer` is required, or a bool where a number is required, is REJECTED. Use
        the SME `criterion` (the plain-English definition / when-to-use / when-NOT) to decide WHICH
        case/finding fields fill WHICH argument. Ground STRICTLY in the DSL excerpt's RUNTIME REALITY
        notes — some documented builtins are unimplemented and will fail. If `prior_feedback` is
        non-empty, FIX exactly what it names (a MISSING required key, a WRONG-TYPE key, or a
        non-compile) and return a corrected full template. Output raw YAML only — no markdown fences,
        no commentary.
        """

        dsl_excerpt: str = dspy.InputField(
            desc="the working subset of the JUTE DSL + idioms (RUNTIME REALITY notes — "
            "some documented builtins are UNIMPLEMENTED and fail at apply; trust these over the spec)"
        )
        criterion: str = dspy.InputField(
            desc="the SME plain-English criterion (definition / when_to_use / when_NOT_to_use) that "
            "says which case/finding fields fill which tool argument"
        )
        input_schema: str = dspy.InputField(
            desc="the tool call's inputSchema (JSON) — the required keys + their types the output "
            "object MUST satisfy exactly"
        )
        sample_input: str = dspy.InputField(
            desc="a sample {case, finding} envelope to draw the argument values from"
        )
        prior_template: str = dspy.InputField(desc="the previous attempt, or '' on the first try")
        prior_feedback: str = dspy.InputField(
            desc="structural feedback on the prior attempt (missing/wrong-type/compile), or ''"
        )
        jute_transform: str = dspy.OutputField(desc="the JUTE transform as raw YAML")

    return JuteArgShapeSignature


def build_argshape_generator(
    client: Any,
    dsl_excerpt: str,
    sample_input: Any,
    *,
    input_schema: dict,
    criterion: str,
    max_iters: int = 3,
    predictor: Any = None,
    seed_template: str = "",
    seed_feedback: str = "",
):
    """Construct a JuteArgShapeGenerator (parallels `jute_extractor.build_extractor_generator`).
    `predictor` is injectable for offline tests (a callable returning an object with
    `.jute_transform`); defaults to a live `dspy.ChainOfThought` over the signature.
    `seed_template`/`seed_feedback` seed iteration 0 (e.g. with a proven shape) so the loop makes a
    MINIMAL edit rather than re-deriving from scratch."""
    import dspy

    class JuteArgShapeGenerator(dspy.Module):
        def __init__(self) -> None:
            super().__init__()
            self.gen = (
                predictor
                if predictor is not None
                else dspy.ChainOfThought(_build_argshape_signature())
            )
            self.client = client
            self.dsl_excerpt = dsl_excerpt
            self.sample_input = sample_input
            self.input_schema = input_schema
            self.criterion = criterion
            self.max_iters = max_iters
            self.seed_template = seed_template
            self.seed_feedback = seed_feedback

        def forward(self, criterion: str | None = None, sample_input: Any = None) -> Any:
            crit = criterion if criterion is not None else self.criterion
            sample = sample_input if sample_input is not None else self.sample_input
            sample = json.loads(sample) if isinstance(sample, str) else sample
            sample_json = json.dumps(sample)
            schema_json = json.dumps(self.input_schema)
            prior_template, prior_feedback = self.seed_template, self.seed_feedback
            history: list[dict] = []
            best: str | None = None
            best_score: dict | None = None
            for it in range(self.max_iters):
                pred = self.gen(
                    dsl_excerpt=self.dsl_excerpt,
                    criterion=crit,
                    input_schema=schema_json,
                    sample_input=sample_json,
                    prior_template=prior_template,
                    prior_feedback=prior_feedback,
                )
                template = strip_fences(getattr(pred, "jute_transform", "") or "")
                s = (
                    score_argshape(self.client, template, sample, input_schema=self.input_schema)
                    if template.strip()
                    else {
                        "accepted": False,
                        "graded": 0.0,
                        "arguments": {},
                        "missing_keys": list(required_keys_of(self.input_schema)),
                        "type_errors": [],
                        "error": "empty template",
                    }
                )
                history.append(
                    {
                        "iter": it,
                        "accepted": s["accepted"],
                        "graded": round(s["graded"], 3),
                        "missing_keys": s["missing_keys"],
                        "type_errors": s["type_errors"],
                    }
                )
                if best_score is None or s["graded"] > best_score["graded"]:
                    best, best_score = template, s
                if s["accepted"]:
                    break
                prior_template = template
                prior_feedback = argshape_feedback_from(s)
            return dspy.Prediction(
                jute_transform=best or "",
                accepted=bool(best_score and best_score["accepted"]),
                score=best_score,
                arguments=(best_score or {}).get("arguments", {}),
                history=history,
            )

    return JuteArgShapeGenerator()


def best_of_n_argshape(make_gen, criterion: str, sample_input: Any, *, n: int = 3) -> Any:
    """Run the argshape refine-loop up to N independent times; return the first invariant-accepted
    prediction, else the highest-graded one (parallels `jute_extractor.best_of_n_extractor`).
    `make_gen` is a 0-arg factory so each attempt is a fresh module instance."""
    best = None
    for _ in range(n):
        pred = make_gen().forward(criterion=criterion, sample_input=sample_input)
        if getattr(pred, "accepted", False):
            return pred
        graded = (getattr(pred, "score", None) or {}).get("graded", 0.0)
        if best is None or graded > (getattr(best, "score", None) or {}).get("graded", 0.0):
            best = pred
    return best
