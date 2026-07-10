"""UAP-2 A2/A4/A5: the prompt↔ontology bridge — render role_key_questions from the
assignment, with the seed ``.txt`` retained as the safety-critical base.

A4 (parity, S-BS-11/44): the DEFAULT (unassigned) render is byte-identical to
``load_role_prompt(role)`` for every v2 role — the safety prose is never silently
dropped, and ``build_trio()`` with no ontology is byte-identical to before (A5).

A2 (the headline — authored lens reaches the judge): an authored assignment's flag
lens + the role's ontology questions render INTO the prompt that ``build_trio``
feeds each ``Judge``'s ``role_key_questions``, so the in-process judge would re-vote
with the authored lens. (The live re-vote is cost-gated, not exercised here.)

No network: ``build_trio`` is driven with injected per-role predictors; only the
``[council]`` extra (openai/tenacity) is needed to import the bridge — skipped
cleanly on the offline core.
"""

from __future__ import annotations

import pytest

pytest.importorskip("openai")
pytest.importorskip("tenacity")

from lithrim_bench.harness.ontology import load_ontology  # noqa: E402
from lithrim_bench.runtime.council.judges_dspy import (  # noqa: E402
    V2_ROLES,
    build_trio,
    load_role_prompt,
    render_role_questions,
)


@pytest.fixture(scope="module")
def ontology():
    return load_ontology()


def _predictors():
    """Trivial per-role predictors (no dspy / no network) — build_trio binds the
    role_prompt we assert; the predictor is never called by these tests."""

    def _p(**_kw):
        return {"decision": "approve", "findings": []}

    return {role: _p for role in V2_ROLES}


# ── A4 parity: the default render == the committed .txt seed ───────────────────


@pytest.mark.parametrize("role", V2_ROLES)
def test_render_default_is_byte_equal_to_txt(ontology, role):
    """The unassigned render returns the seed prompt verbatim — no silent drift of
    safety-critical prose (S-BS-11), .strip() parity (S-BS-44)."""
    assert render_role_questions(ontology, role) == load_role_prompt(role)


@pytest.mark.parametrize("role", V2_ROLES)
def test_build_trio_no_ontology_is_byte_identical(role):
    """build_trio() with no ontology binds each judge's council_roles/<role>.txt
    verbatim — back-compat A5 (the bridge is purely additive when unused)."""
    judges = {j.role: j for j in build_trio(predictors=_predictors())}
    assert judges[role].role_prompt == load_role_prompt(role)


@pytest.mark.parametrize("role", V2_ROLES)
def test_build_trio_with_ontology_unassigned_equals_txt(ontology, role):
    """Even on the ontology path, a role with no assignment renders to the seed
    .txt (the default trio assignment renders semantically-equivalent — A4)."""
    judges = {j.role: j for j in build_trio(predictors=_predictors(), ontology=ontology)}
    assert judges[role].role_prompt == load_role_prompt(role)


# ── A2: the authored lens reaches the judge prompt ────────────────────────────


def test_render_authored_lens_and_questions_reach_the_prompt(ontology):
    out = render_role_questions(
        ontology, "risk_judge", assigned_flags=["WRONG_DOSAGE", "FABRICATED_ALLERGY"]
    )
    # base retained verbatim, refinement appended
    assert out.startswith(load_role_prompt("risk_judge"))
    assert "AUTHORED REFINEMENT (ontology assignment)" in out
    assert "WRONG_DOSAGE" in out and "FABRICATED_ALLERGY" in out
    # the role's ontology questions are rendered, ordinal-ordered
    assert "Refinement questions for this role:" in out
    assert "1. " in out
    # the assigned flags' when_to_use lens is carried (a substring of the WRONG_DOSAGE def)
    fd = ontology.flag("WRONG_DOSAGE")
    assert fd.when_to_use[:24] in out


def test_build_trio_assignment_feeds_role_key_questions(ontology):
    """The headline: an authored assignment renders into the prompt build_trio binds
    to the Judge — i.e. the judge's role_key_questions carry the authored lens."""
    judges = {
        j.role: j
        for j in build_trio(
            predictors=_predictors(),
            ontology=ontology,
            assignments={"policy_judge": ["FABRICATED_CONSENT"]},
        )
    }
    policy = judges["policy_judge"].role_prompt
    assert "AUTHORED REFINEMENT (ontology assignment)" in policy
    assert "FABRICATED_CONSENT" in policy
    # an unassigned sibling role still renders to its seed (no cross-contamination)
    assert judges["risk_judge"].role_prompt == load_role_prompt("risk_judge")


def test_render_lens_only_when_role_has_no_ontology_questions(ontology):
    """faithfulness_judge has zero seeded ontology questions (the seed predates the
    v2 trio) — the refinement is lens-only; the questions block is omitted, not faked."""
    out = render_role_questions(ontology, "faithfulness_judge", assigned_flags=["MISSING_ALLERGY"])
    assert "MISSING_ALLERGY" in out
    assert "Refinement questions for this role:" not in out
