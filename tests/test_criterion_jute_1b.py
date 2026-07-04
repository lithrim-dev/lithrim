"""CRITERION-JUTE-1b — argshape generator/scorer (the 1a wire's authoring-time twin).

Networkless: :3031 is not required. A FAKE client stands in for ``EtlpJuteClient``
(``test_template`` returns a canned ``{compiled, output}`` per test) and an injected
predictor stands in for ``dspy.ChainOfThought`` (a callable returning an object with a
``.jute_transform`` attr). The scorer's whole point is the output-invariant: the applied
JUTE OUTPUT must be a single JSON OBJECT matching the tool call's inputSchema (every
``required`` key present, non-null, correctly typed).
"""

from __future__ import annotations

from types import SimpleNamespace

from lithrim_bench.verification.jute_argshape import (
    argshape_feedback_from,
    best_of_n_argshape,
    build_argshape_generator,
    make_argshape_metric,
    required_keys_of,
    schema_type_of,
    score_argshape,
)

# the REAL envelope the 1a grade-time wire applies (grounding._shape_arguments):
#   test_template(jute, {"case": case, "finding": finding})  ->  resource.case.* / resource.finding.*
SAMPLE_INPUT = {
    "case": {"pinned": {"subsumption": {"record_snomed": "52448006", "note_snomed": "26929004"}}},
    "finding": {"flag_code": "FABRICATED_HISTORY", "span": "bacterial pneumonia"},
}

# the tool call's inputSchema (what 1d reads live via McpStdioClient.list_tools and hands in).
INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "concept_id": {"type": "integer"},
        "subsumer_id": {"type": "integer"},
    },
    "required": ["concept_id", "subsumer_id"],
}

GOOD_ARGS = {"concept_id": 52448006, "subsumer_id": 26929004}


class FakeClient:
    """A stand-in for EtlpJuteClient — ``test_template`` returns the canned response keyed by the
    template string (the tests pass a template that just names the case they want)."""

    def __init__(self, responses: dict[str, dict]):
        self._responses = responses

    def test_template(self, template: str, sample_input) -> dict:
        return self._responses[template]


def _compiled(output) -> dict:
    return {"compiled": True, "output": output}


def _uncompiled(error: str = "syntax") -> dict:
    return {"compiled": False, "output": None, "error": error}


# --------------------------------------------------------------------------- #
# required_keys_of / schema_type_of helpers
# --------------------------------------------------------------------------- #
def test_required_keys_of_reads_schema():
    assert required_keys_of(INPUT_SCHEMA) == ("concept_id", "subsumer_id")
    assert required_keys_of({"type": "object", "properties": {}}) == ()
    assert required_keys_of({}) == ()


def test_schema_type_of_reads_property_type():
    assert schema_type_of(INPUT_SCHEMA, "concept_id") == "integer"
    assert schema_type_of(INPUT_SCHEMA, "nope") is None


# --------------------------------------------------------------------------- #
# 1. accepts a fully-correct output
# --------------------------------------------------------------------------- #
def test_score_argshape_accepts_correct_output():
    client = FakeClient({"T": _compiled(GOOD_ARGS)})
    s = score_argshape(client, "T", SAMPLE_INPUT, input_schema=INPUT_SCHEMA)
    assert s["accepted"] is True
    assert s["graded"] == 1.0
    assert s["arguments"] == GOOD_ARGS
    assert s["missing_keys"] == []
    assert s["type_errors"] == []
    assert s["error"] is None


# --------------------------------------------------------------------------- #
# 2. missing a required key
# --------------------------------------------------------------------------- #
def test_score_argshape_missing_required_key():
    client = FakeClient({"T": _compiled({"concept_id": 52448006})})
    s = score_argshape(client, "T", SAMPLE_INPUT, input_schema=INPUT_SCHEMA)
    assert s["accepted"] is False
    assert "subsumer_id" in s["missing_keys"]
    assert s["graded"] < 1.0
    assert s["arguments"] == {}


# --------------------------------------------------------------------------- #
# 3. null on a required key
# --------------------------------------------------------------------------- #
def test_score_argshape_null_required_key_rejected():
    client = FakeClient({"T": _compiled({"concept_id": 52448006, "subsumer_id": None})})
    s = score_argshape(client, "T", SAMPLE_INPUT, input_schema=INPUT_SCHEMA)
    assert s["accepted"] is False
    assert "subsumer_id" in s["missing_keys"]
    assert s["graded"] < 1.0


# --------------------------------------------------------------------------- #
# 4. wrong type — string where integer required, AND bool-is-not-integer
# --------------------------------------------------------------------------- #
def test_score_argshape_string_where_integer_rejected():
    client = FakeClient({"T": _compiled({"concept_id": "52448006", "subsumer_id": 26929004})})
    s = score_argshape(client, "T", SAMPLE_INPUT, input_schema=INPUT_SCHEMA)
    assert s["accepted"] is False
    assert "concept_id" in s["type_errors"]
    assert s["graded"] < 1.0


def test_score_argshape_bool_is_not_integer():
    client = FakeClient({"T": _compiled({"concept_id": True, "subsumer_id": 26929004})})
    s = score_argshape(client, "T", SAMPLE_INPUT, input_schema=INPUT_SCHEMA)
    assert s["accepted"] is False
    assert "concept_id" in s["type_errors"]


def test_score_argshape_number_accepts_int_and_float():
    schema = {
        "type": "object",
        "properties": {"score": {"type": "number"}},
        "required": ["score"],
    }
    assert (
        score_argshape(
            FakeClient({"T": _compiled({"score": 3})}), "T", SAMPLE_INPUT, input_schema=schema
        )["accepted"]
        is True
    )
    assert (
        score_argshape(
            FakeClient({"T": _compiled({"score": 3.5})}), "T", SAMPLE_INPUT, input_schema=schema
        )["accepted"]
        is True
    )
    assert (
        score_argshape(
            FakeClient({"T": _compiled({"score": True})}), "T", SAMPLE_INPUT, input_schema=schema
        )["accepted"]
        is False
    )


# --------------------------------------------------------------------------- #
# 5. non-dict output (array / scalar / None) and a non-compile — NEVER raises
# --------------------------------------------------------------------------- #
def test_score_argshape_array_output_rejected_never_raises():
    client = FakeClient({"T": _compiled([GOOD_ARGS])})
    s = score_argshape(client, "T", SAMPLE_INPUT, input_schema=INPUT_SCHEMA)
    assert s["accepted"] is False
    assert s["graded"] == 0.0
    assert s["arguments"] == {}


def test_score_argshape_scalar_output_rejected():
    s = score_argshape(
        FakeClient({"T": _compiled(42)}), "T", SAMPLE_INPUT, input_schema=INPUT_SCHEMA
    )
    assert s["accepted"] is False
    assert s["graded"] == 0.0


def test_score_argshape_none_output_rejected():
    s = score_argshape(
        FakeClient({"T": _compiled(None)}), "T", SAMPLE_INPUT, input_schema=INPUT_SCHEMA
    )
    assert s["accepted"] is False
    assert s["graded"] == 0.0


def test_score_argshape_uncompiled_rejected_with_error():
    s = score_argshape(
        FakeClient({"T": _uncompiled("boom")}), "T", SAMPLE_INPUT, input_schema=INPUT_SCHEMA
    )
    assert s["accepted"] is False
    assert s["graded"] == 0.0
    assert s["error"] == "boom"


# --------------------------------------------------------------------------- #
# 6. argshape_feedback_from names the exact failure
# --------------------------------------------------------------------------- #
def test_feedback_names_missing_key():
    client = FakeClient({"T": _compiled({"concept_id": 52448006})})
    s = score_argshape(client, "T", SAMPLE_INPUT, input_schema=INPUT_SCHEMA)
    fb = argshape_feedback_from(s)
    assert "subsumer_id" in fb


def test_feedback_names_wrong_type():
    client = FakeClient({"T": _compiled({"concept_id": "52448006", "subsumer_id": 26929004})})
    s = score_argshape(client, "T", SAMPLE_INPUT, input_schema=INPUT_SCHEMA)
    fb = argshape_feedback_from(s)
    assert "concept_id" in fb
    assert "integer" in fb.lower()


def test_feedback_names_did_not_compile():
    s = score_argshape(
        FakeClient({"T": _uncompiled("bad yaml")}), "T", SAMPLE_INPUT, input_schema=INPUT_SCHEMA
    )
    fb = argshape_feedback_from(s)
    assert "compile" in fb.lower()


def test_feedback_all_good():
    client = FakeClient({"T": _compiled(GOOD_ARGS)})
    s = score_argshape(client, "T", SAMPLE_INPUT, input_schema=INPUT_SCHEMA)
    assert argshape_feedback_from(s)  # non-empty confirmation string


# --------------------------------------------------------------------------- #
# 7. build_argshape_generator — bad then good candidate converges
# --------------------------------------------------------------------------- #
class _ScriptedPredictor:
    """Emits a scripted sequence of templates, one per .forward call, cycling on the last."""

    def __init__(self, templates: list[str]):
        self._templates = templates
        self._i = 0

    def __call__(self, **kwargs):
        t = self._templates[min(self._i, len(self._templates) - 1)]
        self._i += 1
        return SimpleNamespace(jute_transform=t)


def test_generator_converges_bad_then_good():
    client = FakeClient(
        {
            "BAD": _compiled({"concept_id": 52448006}),  # missing subsumer_id
            "GOOD": _compiled(GOOD_ARGS),
        }
    )
    predictor = _ScriptedPredictor(["BAD", "GOOD"])
    gen = build_argshape_generator(
        client,
        dsl_excerpt="DSL",
        sample_input=SAMPLE_INPUT,
        input_schema=INPUT_SCHEMA,
        criterion="record term subsumes note term",
        predictor=predictor,
        max_iters=3,
    )
    pred = gen.forward(criterion="record term subsumes note term")
    assert pred.accepted is True
    assert pred.arguments == GOOD_ARGS
    assert len(pred.history) == 2
    assert pred.history[0]["accepted"] is False
    assert pred.history[1]["accepted"] is True


def test_generator_never_accepts_all_bad():
    client = FakeClient({"BAD": _compiled({"concept_id": 52448006})})
    predictor = _ScriptedPredictor(["BAD"])
    gen = build_argshape_generator(
        client,
        dsl_excerpt="DSL",
        sample_input=SAMPLE_INPUT,
        input_schema=INPUT_SCHEMA,
        criterion="crit",
        predictor=predictor,
        max_iters=2,
    )
    pred = gen.forward(criterion="crit")
    assert pred.accepted is False
    assert len(pred.history) == 2


# --------------------------------------------------------------------------- #
# 8. best_of_n_argshape returns first accepted; else highest-graded
# --------------------------------------------------------------------------- #
def test_best_of_n_returns_first_accepted():
    client = FakeClient({"GOOD": _compiled(GOOD_ARGS)})

    def make_gen():
        return build_argshape_generator(
            client,
            dsl_excerpt="DSL",
            sample_input=SAMPLE_INPUT,
            input_schema=INPUT_SCHEMA,
            criterion="crit",
            predictor=_ScriptedPredictor(["GOOD"]),
            max_iters=1,
        )

    pred = best_of_n_argshape(make_gen, "crit", SAMPLE_INPUT, n=3)
    assert pred.accepted is True
    assert pred.arguments == GOOD_ARGS


def test_best_of_n_returns_highest_graded_when_none_accepted():
    # WORSE misses both required keys (graded 0); LESSBAD misses one (graded 0.5)
    client = FakeClient(
        {
            "WORSE": _compiled({}),
            "LESSBAD": _compiled({"concept_id": 52448006}),
        }
    )
    scripts = iter([["WORSE"], ["LESSBAD"], ["WORSE"]])

    def make_gen():
        return build_argshape_generator(
            client,
            dsl_excerpt="DSL",
            sample_input=SAMPLE_INPUT,
            input_schema=INPUT_SCHEMA,
            criterion="crit",
            predictor=_ScriptedPredictor(next(scripts)),
            max_iters=1,
        )

    pred = best_of_n_argshape(make_gen, "crit", SAMPLE_INPUT, n=3)
    assert pred.accepted is False
    assert pred.score["graded"] == 0.5


# --------------------------------------------------------------------------- #
# 9. make_argshape_metric — hard bool under trace, float otherwise
# --------------------------------------------------------------------------- #
def test_metric_hard_bool_under_trace():
    client = FakeClient({"GOOD": _compiled(GOOD_ARGS), "BAD": _compiled({})})
    metric = make_argshape_metric(client, SAMPLE_INPUT, input_schema=INPUT_SCHEMA)
    good = metric(None, SimpleNamespace(jute_transform="GOOD"), trace=object())
    bad = metric(None, SimpleNamespace(jute_transform="BAD"), trace=object())
    assert good is True
    assert bad is False


def test_metric_graded_float_without_trace():
    client = FakeClient({"HALF": _compiled({"concept_id": 52448006})})
    metric = make_argshape_metric(client, SAMPLE_INPUT, input_schema=INPUT_SCHEMA)
    v = metric(None, SimpleNamespace(jute_transform="HALF"), trace=None)
    assert isinstance(v, float)
    assert v == 0.5


def test_metric_empty_template():
    client = FakeClient({})
    metric = make_argshape_metric(client, SAMPLE_INPUT, input_schema=INPUT_SCHEMA)
    assert metric(None, SimpleNamespace(jute_transform=""), trace=object()) is False
    assert metric(None, SimpleNamespace(jute_transform=""), trace=None) == 0.0
