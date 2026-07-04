"""Close the DSPy judge loop — optimize one judge against the bench-accept metric
on the by-construction calibration corpus, then measure compiled-vs-baseline on a
held-out split (WS-6c-DSPy-3b, bench-salvage).

The loop is: judges-as-modules (``judges_dspy.Judge``) → a bench-accept *metric*
(``judge_metric.make_judge_metric``) → a recipe=label *corpus*
(``examples/judge_calib_v1.jsonl``) → **optimize** (this module) → **measure** the
held-out Δ → **bind back** the compiled demos into a production ``Judge``. The
first three exist; this module adds the last three for ONE judge (``risk_judge``,
the rebuilt-first judge with the most positives).

DSPy lives strictly ABOVE the per-judge seam. ``JudgeProgram`` is a SEPARATE,
ADDITIVE compilable view of a judge: it wraps the SAME ``JudgeSignature`` as
``Judge.predict`` (so demos compiled here transfer to the production ``Judge``) and
runs the SAME ``_validate_findings`` projection in ``forward`` (so the compile gate
and the held-out eval score the production-faithful findings the bound-back judge
would actually emit). The frozen consensus IP (``compliance_council``) is untouched
— optimizing a judge prompt can never weaken a Tier-1 rule, which lives below this
layer (``RECOMPOSITION_PLAN_ws6.md`` §6).

Import discipline (A3): this module is import-safe on the DEFAULT pydantic+pandas
core. ``judges_dspy`` pulls ``compliance_council`` which ``import openai`` at module
top, so EVERY council/dspy symbol is imported LAZILY inside the function that needs
it. Top-level imports are restricted to ``judge_metric`` (pure) and
``ab_harness._artifact_text`` (ab_harness top-imports only ``judge_metric``), so
``import judge_optimize`` leaves ``dspy``/``openai`` out of ``sys.modules``.
``_example_fields`` / ``load_corpus`` / ``evaluate_program`` / ``bind_compiled_demos``
are therefore exercisable offline ($0, no dspy/openai).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .ab_harness import _artifact_text
from .judge_metric import LENS_BY_ROLE, expected_codes, make_judge_metric, score_judge

_SIGNATURE_INPUTS = ("transcript", "artifact", "role_key_questions", "taxonomy_context")


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# --------------------------------------------------------------------------- #
# corpus loading + lens-filtering (pure — no dspy / openai)
# --------------------------------------------------------------------------- #
def load_corpus(path: str | Path, *, split: str | None = None) -> list[dict[str, Any]]:
    """Read ``judge_calib_v1.jsonl`` (one JSON object per line), optionally keeping
    only rows whose ``split`` matches (``"calibration"`` = trainset, ``"test"`` =
    held-out). No dspy needed."""
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if split is None or row.get("split") == split:
                rows.append(row)
    return rows


def role_relevant(row: Any, lens: Iterable[str]) -> bool:
    """Whether a corpus row belongs in a judge's train/held-out set (D4).

    Keep a row if it carries an in-lens label (this judge's recall target) OR is a
    clean negative (it measures over-fire — the calibration-trainer's whole point).
    A row whose only labels are out-of-lens (another judge's domain) is dropped —
    it is not this judge's recall target."""
    expected = expected_codes(row)
    lens = set(lens)
    return bool(expected & lens) or not expected


# --------------------------------------------------------------------------- #
# corpus row -> DSPy example projection
# --------------------------------------------------------------------------- #
def _example_fields(
    row: dict[str, Any], *, role_prompt: str, taxonomy_context: str
) -> dict[str, Any]:
    """Pure projection of a corpus row into the signature's input fields + the
    recipe label the metric scores against. Takes ``role_prompt`` /
    ``taxonomy_context`` as args (rather than resolving them via the openai-pulling
    ``judges_dspy``) so it is testable offline on the default core."""
    return {
        "transcript": row.get("transcript", ""),
        "artifact": _artifact_text(row),
        "role_key_questions": role_prompt,
        "taxonomy_context": taxonomy_context,
        "expected_safety_flags": list(row.get("expected_safety_flags") or []),
    }


def build_examples(rows: Iterable[dict[str, Any]], *, role: str) -> list[Any]:
    """Project corpus rows into ``dspy.Example``s with the signature inputs marked.

    The ``expected_safety_flags`` field rides along (not an input) so the metric can
    read the recipe label. ``dspy`` + the role prompt/taxonomy are resolved lazily."""
    import dspy

    from .judges_dspy import default_taxonomy_context, load_role_prompt

    role_prompt = load_role_prompt(role)
    taxonomy_context = default_taxonomy_context()
    examples: list[Any] = []
    for row in rows:
        fields = _example_fields(row, role_prompt=role_prompt, taxonomy_context=taxonomy_context)
        examples.append(dspy.Example(**fields).with_inputs(*_SIGNATURE_INPUTS))
    return examples


# --------------------------------------------------------------------------- #
# coverage-aware demo selection (S-BS-49) — pure, additive, no dspy/openai
# --------------------------------------------------------------------------- #
def _example_raises_in_lens(example: Any, lens: Iterable[str]) -> bool:
    """Whether an example is an in-lens POSITIVE (a defect this judge must catch) —
    i.e. carries ≥1 ``expected_safety_flag`` inside the role's lens. A clean negative
    (no expected flags) or an out-of-lens-only row is NOT a positive exemplar."""
    flags = set(_get(example, "expected_safety_flags", None) or [])
    return bool(flags & set(lens))


def order_positive_first(trainset: list[Any], *, lens: Iterable[str]) -> list[Any]:
    """Reorder a trainset so in-lens POSITIVES come first, preserving relative order
    within each group (S-BS-49 coverage-aware demo selection).

    ``BootstrapFewShot`` iterates the trainset in order, keeping only cases the teacher
    nails exactly (the hard-accept gate) until ``max_bootstrapped_demos`` is reached. On
    the small mixed ``judge_calib_v1`` corpus the first-accepted cases happen to be the
    SILENT clean ones, so positives never get a slot → 0 positive exemplars → over-fire
    (the WS-6c-DSPy-3b negative Δ). Surfacing positives first gives every nailable
    positive first crack at a demo slot WITHOUT touching the accept-gate
    (``judge_metric`` is FROZEN) and WITHOUT extra teacher calls (a single compile pass).
    Guarantee: if the teacher can perfectly judge ≥1 in-lens positive, the compiled
    demos carry ≥1 positive exemplar. It cannot manufacture a win — a teacher that nails
    no positive still yields none, honestly."""
    lens = set(lens)
    positives = [ex for ex in trainset if _example_raises_in_lens(ex, lens)]
    rest = [ex for ex in trainset if not _example_raises_in_lens(ex, lens)]
    return positives + rest


def _demo_raises(demo: Any) -> bool:
    """A compiled demo is a non-silent (raising) exemplar iff it carries ≥1 finding —
    the property S-BS-49 says the harvested demos all LACKED (all silent)."""
    return bool(_get(demo, "findings", None))


# --------------------------------------------------------------------------- #
# JudgeProgram — the compilable, production-faithful view of a judge
# --------------------------------------------------------------------------- #
def build_judge_program(*, lm: Any = None, predictor: Any = None) -> Any:
    """Construct a ``JudgeProgram`` (a ``dspy.Module``) — defined lazily so importing
    this module never pulls ``dspy`` (A3).

    The program wraps one ``dspy.Predict(JudgeSignature)`` — the SAME signature
    ``Judge.predict`` wraps, so the bootstrapped demos compiled onto this program
    transfer to a production ``Judge``. ``forward`` runs the SAME
    ``_validate_findings`` projection ``Judge.forward`` runs, so the metric scores
    the production-faithful findings (ungrounded / off-taxonomy findings dropped) —
    the compile gate and held-out eval reflect what the bound-back judge emits.

    Offline: pass ``predictor`` (a callable returning an object/dict with
    ``decision``/``findings``) to construct without ``dspy``. Live: pass ``lm``.
    """
    import dspy

    from .judges_dspy import _build_signature, _norm_decision, _validate_findings

    class JudgeProgram(dspy.Module):
        def __init__(self, *, predictor: Any = None, lm: Any = None) -> None:
            super().__init__()
            if predictor is not None:
                self.predict = predictor
            else:
                self.predict = dspy.Predict(_build_signature())
                if lm is not None:
                    self.predict.set_lm(lm)

        def forward(
            self,
            transcript: str,
            artifact: str,
            role_key_questions: str,
            taxonomy_context: str,
        ) -> Any:
            pred = self.predict(
                transcript=transcript,
                artifact=artifact,
                role_key_questions=role_key_questions,
                taxonomy_context=taxonomy_context,
            )
            findings = _validate_findings(_get(pred, "findings", []))
            return dspy.Prediction(
                decision=_norm_decision(_get(pred, "decision")),
                findings=findings,
                reason=_get(pred, "reason", ""),
            )

    return JudgeProgram(predictor=predictor, lm=lm)


# --------------------------------------------------------------------------- #
# evaluate + optimize
# --------------------------------------------------------------------------- #
def evaluate_program(
    program: Any,
    cases: Iterable[dict[str, Any]],
    *,
    role: str,
    role_prompt: str | None = None,
    taxonomy_context: str | None = None,
    co_raise_aware: bool = True,
) -> dict[str, Any]:
    """Score a ``JudgeProgram`` (or any object with a matching ``forward``) on
    ``cases`` via ``score_judge`` on the role's lens. Used identically for the
    baseline (un-compiled) and compiled programs → the held-out Δ.

    ``role_prompt`` / ``taxonomy_context`` are resolved lazily via ``judges_dspy``
    when not supplied (live path); offline callers pass them explicitly to avoid the
    council import chain. ``co_raise_aware=True`` (S-BS-43) lifts the per-judge
    precision lower bound (a corroborating raise of another owner's expected code is
    neutral, not an FP)."""
    if role_prompt is None or taxonomy_context is None:
        from .judges_dspy import default_taxonomy_context, load_role_prompt

        role_prompt = role_prompt if role_prompt is not None else load_role_prompt(role)
        taxonomy_context = (
            taxonomy_context if taxonomy_context is not None else default_taxonomy_context()
        )

    def run_judge(case: dict[str, Any]) -> Any:
        # call the program (not .forward) so a dspy.Module resolves its LM via the
        # ambient dspy.context the live caller sets — a compiled program is a
        # deepcopy whose per-predictor LM binding is dropped, so it relies on the
        # context, not set_lm. Offline fakes are plain callables (__call__).
        return program(
            transcript=case.get("transcript", ""),
            artifact=_artifact_text(case),
            role_key_questions=role_prompt,
            taxonomy_context=taxonomy_context,
        )

    return score_judge(
        run_judge, cases, lens_codes=LENS_BY_ROLE[role], co_raise_aware=co_raise_aware
    )


def compile_judge(
    role: str,
    trainset: list[Any],
    *,
    lm: Any = None,
    predictor: Any = None,
    max_bootstrapped_demos: int = 4,
    max_labeled_demos: int = 0,
    coverage_aware: bool = False,
) -> Any:
    """Compile a ``JudgeProgram`` with ``BootstrapFewShot`` on ``trainset``.

    The metric is ``make_judge_metric(lens_codes=LENS_BY_ROLE[role],
    co_raise_aware=True)`` — with ``trace`` set it returns the hard-accept bool, so
    ONLY a per-case-perfect (production-faithful) judgement becomes a bootstrapped
    demo. ``max_labeled_demos=0`` by design: our corpus examples carry the metric
    label (``expected_safety_flags``), NOT gold ``JudgeSignature`` outputs
    (``decision``/``findings``/``reason``), so labeled demos are degenerate in dspy
    3.2.1 — only bootstrapped demos (real traced signature I/O kept iff the gate
    passes) are valid few-shot exemplars here.

    ``coverage_aware=True`` (S-BS-49) reorders the trainset so in-lens positives come
    first (``order_positive_first``) — a single-pass, accept-gate-preserving change
    that gives nailable positives first crack at the demo slots. It cannot loosen the
    gate or manufacture a win."""
    import dspy

    if coverage_aware:
        trainset = order_positive_first(trainset, lens=LENS_BY_ROLE[role])
    program = build_judge_program(lm=lm, predictor=predictor)
    metric = make_judge_metric(lens_codes=LENS_BY_ROLE[role], co_raise_aware=True)
    teleprompter = dspy.teleprompt.BootstrapFewShot(
        metric=metric,
        max_bootstrapped_demos=max_bootstrapped_demos,
        max_labeled_demos=max_labeled_demos,
    )
    if lm is not None:
        with dspy.context(lm=lm):
            return teleprompter.compile(program, trainset=trainset)
    return teleprompter.compile(program, trainset=trainset)


def bind_compiled_demos(judge: Any, program: Any) -> Any:
    """Copy the compiled few-shot demos off ``program.predict`` onto ``judge``'s
    ``predict.demos`` — the loop's closing move: an optimized judge can become the
    production judge. Duck-typed (operates on ``.predict.demos``) so it is testable
    offline with stubs (importing the real ``Judge`` pulls ``openai``).

    This is the MECHANISM only (WS-6c-DSPy-3b). Flipping ``build_trio`` to load demos
    by default is a production-behavior change → a follow-up cycle (S-BS-48)."""
    demos = list(getattr(program.predict, "demos", []) or [])
    judge.predict.demos = demos
    return judge


# --------------------------------------------------------------------------- #
# the paid entrypoint
# --------------------------------------------------------------------------- #
def _serialize_demos(program: Any) -> list[dict[str, Any]]:
    demos = getattr(getattr(program, "predict", None), "demos", []) or []
    out: list[dict[str, Any]] = []
    for d in demos:
        to_dict = getattr(d, "toDict", None)
        out.append(to_dict() if callable(to_dict) else dict(d))
    return out


# DEMO-PIN-1 (S-BS-48): the inverse of _serialize_demos + a workspace discovery helper — the
# load side of "optimize writes compiled_demos_<tag>_<role>.json, the next grade uses them".
_DEMO_INPUT_FIELDS = ("transcript", "artifact", "role_key_questions", "taxonomy_context")


def deserialize_demos(rows: list[dict[str, Any]]) -> list[Any]:
    """Rebuild ``dspy.Example`` few-shot demos from the serialized rows _serialize_demos wrote.

    The four judge-signature INPUTS are marked via ``.with_inputs`` so DSPy formats each demo as a
    proper few-shot exemplar (inputs shown, outputs — decision/findings/reason — as the target)."""
    import dspy

    return [dspy.Example(**row).with_inputs(*_DEMO_INPUT_FIELDS) for row in rows]


def load_compiled_demos(out_dir: Any, role: str) -> list[Any] | None:
    """The compiled demos for ``role`` under ``out_dir`` (the workspace out-dir a grade writes to),
    deserialized — or ``None`` when this workspace has no optimized judge for the role (the grade
    then runs demo-less, byte-identical to before). Picks the lexicographically-last match so a
    re-optimize's fresh file wins; a role with no file never cross-reads another role's demos."""
    from pathlib import Path

    hits = sorted(Path(out_dir).glob(f"compiled_demos_*_{role}.json"))
    if not hits:
        return None
    rows = json.loads(hits[-1].read_text(encoding="utf-8"))
    return deserialize_demos(rows) or None


def _delta(baseline: dict[str, Any], optimized: dict[str, Any]) -> dict[str, Any]:
    keys = ("graded", "precision", "recall")
    delta = {k: round(optimized[k] - baseline[k], 4) for k in keys}
    delta["accepted"] = (baseline["accepted"], optimized["accepted"])
    delta["tp_fp_fn"] = {
        "baseline": [baseline["tp"], baseline["fp"], baseline["fn"]],
        "optimized": [optimized["tp"], optimized["fp"], optimized["fn"]],
    }
    return delta


def run_optimize(
    role: str = "risk_judge",
    *,
    corpus_path: str | Path,
    confirm_cost: bool = False,
    out_dir: str | Path,
    limit: int | None = None,
    max_bootstrapped_demos: int = 4,
    max_labeled_demos: int = 0,
    coverage_aware: bool = False,
) -> dict[str, Any]:
    """The PAID entrypoint: optimize ``role`` on the calibration split, measure the
    held-out Δ on the test split, persist the compiled demos + both score dicts.

    Refuses without ``confirm_cost=True`` (the standing cost-confirm rule, mirroring
    ``ab_harness.run_live``). ``limit`` caps each split for the smoke (per-call cost
    check). Returns ``{role, n_train, n_heldout, baseline, optimized, delta}``. A
    measured Δ — including ≤0, or 0 demos bootstrapped — is the loop-closure; the
    gate is never loosened to manufacture a win."""
    if not confirm_cost:
        raise RuntimeError(
            "run_optimize makes paid Azure calls (bootstrap over the trainset + "
            "two held-out evals × the judge); pass confirm_cost=True only after an "
            "explicit cost check"
        )

    # Holdout hygiene (REL-OPS-1 O6, docs/POLICY_HOLDOUT_HYGIENE.md): only `calibration`
    # rows may tune. A corpus with no calibration rows is certify-only — refuse HERE,
    # before `import dspy` / LM construction, so no paid work and no possibility of the
    # held-out `test` split leaking into the trainset.
    rows = load_corpus(corpus_path)
    if not any(r.get("split") == "calibration" for r in rows):
        raise ValueError(
            f"certify-only corpus: {corpus_path} carries no `split == \"calibration\"` rows. "
            "The held-out `test` split may CERTIFY a judge, never tune it "
            "(docs/POLICY_HOLDOUT_HYGIENE.md); refusing before any paid call."
        )

    import dspy

    from .judges_dspy import build_judge_lm, default_taxonomy_context, load_role_prompt

    lens = LENS_BY_ROLE[role]
    train_rows = [r for r in rows if r.get("split") == "calibration" and role_relevant(r, lens)]
    heldout_rows = [r for r in rows if r.get("split") == "test" and role_relevant(r, lens)]
    if limit is not None:
        train_rows = train_rows[:limit]
        heldout_rows = heldout_rows[:limit]

    lm = build_judge_lm(role)
    role_prompt = load_role_prompt(role)
    taxonomy_context = default_taxonomy_context()

    # one ambient LM for the whole live section: the baseline program, the
    # BootstrapFewShot compile, and the compiled program (a deepcopy whose
    # per-predictor LM binding is dropped) all resolve their LM from this context.
    with dspy.context(lm=lm):
        baseline_program = build_judge_program()
        baseline = evaluate_program(
            baseline_program,
            heldout_rows,
            role=role,
            role_prompt=role_prompt,
            taxonomy_context=taxonomy_context,
        )

        trainset = build_examples(train_rows, role=role)
        compiled = compile_judge(
            role,
            trainset,
            max_bootstrapped_demos=max_bootstrapped_demos,
            max_labeled_demos=max_labeled_demos,
            coverage_aware=coverage_aware,
        )
        optimized = evaluate_program(
            compiled,
            heldout_rows,
            role=role,
            role_prompt=role_prompt,
            taxonomy_context=taxonomy_context,
        )

    demos = _serialize_demos(compiled)
    n_positive_demos = sum(1 for d in demos if d.get("findings"))
    result = {
        "role": role,
        "n_train": len(train_rows),
        "n_heldout": len(heldout_rows),
        "compile_config": {
            "max_bootstrapped_demos": max_bootstrapped_demos,
            "max_labeled_demos": max_labeled_demos,
            "co_raise_aware": True,
            "coverage_aware": coverage_aware,
            "n_demos_bootstrapped": len(demos),
            "n_positive_demos": n_positive_demos,
        },
        "baseline": baseline,
        "optimized": optimized,
        "delta": _delta(baseline, optimized),
    }

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"dspy3b_{role}"
    (out_dir / f"compiled_demos_{tag}.json").write_text(
        json.dumps(demos, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / f"score_baseline_{tag}.json").write_text(
        json.dumps(baseline, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / f"score_optimized_{tag}.json").write_text(
        json.dumps(optimized, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / f"result_{tag}.json").write_text(
        json.dumps({k: v for k, v in result.items() if k not in ("baseline", "optimized")}, indent=2, default=str),
        encoding="utf-8",
    )
    return result
