"""SERVED-MODEL-2: an arm cannot report a model it did not run on.

Found 2026-09-16 in the paid OpenAI reproduction of v0.1.31: `lithrim configure --model
openai/gpt-4.1-2025-04-14` never reached the council (MODEL-BIND-1), so 90 cases graded on
gpt-4o-2024-08-06 — and `_grade_and_score` wrote that straight into arm_manifest.json beside
`pinned_by: "dated model id"` without a word. The observation was recorded and never CHECKED.

A dated model id is a promise about which model answered, so a served id that is not it fails
the arm. A deployment name or an operator attestation is not comparable to a served id (an
Azure deployment legitimately reports the model it serves), so those are reported, not refused."""

from __future__ import annotations

import pytest

from lithrim_bench.cli.loop import served_model_mismatch


def test_a_dated_pin_matched_by_the_served_id_is_fine():
    assert served_model_mismatch(
        {"gpt-4.1-2025-04-14": 90}, model="openai/gpt-4.1-2025-04-14", dated=True
    ) is None


def test_a_different_model_family_under_a_dated_pin_is_a_mismatch():
    reason = served_model_mismatch(
        {"gpt-4o-2024-08-06": 90}, model="openai/gpt-4.1-2025-04-14", dated=True
    )
    assert reason and "gpt-4o-2024-08-06" in reason and "gpt-4.1-2025-04-14" in reason


def test_a_different_dated_version_of_the_same_family_is_still_a_mismatch():
    assert served_model_mismatch(
        {"gpt-4.1-2025-01-01": 5}, model="openai/gpt-4.1-2025-04-14", dated=True
    )


def test_two_served_versions_inside_one_arm_is_a_mismatch():
    reason = served_model_mismatch(
        {"gpt-4.1-2025-04-14": 60, "gpt-4o-2024-08-06": 30}, model="openai/gpt-4.1-2025-04-14",
        dated=True,
    )
    assert reason and "2 served" in reason


def test_an_unobserved_arm_is_not_accused():
    """No served_model on any vote (an older service, a $0 replay) is unknown, not a mismatch."""
    assert served_model_mismatch({"None": 90}, model="openai/gpt-4.1-2025-04-14", dated=True) is None
    assert served_model_mismatch({}, model="openai/gpt-4.1-2025-04-14", dated=True) is None


def test_a_deployment_pin_is_reported_not_refused():
    """An Azure deployment name is not comparable to the served model id it answers with."""
    assert served_model_mismatch(
        {"gpt-4.1-2025-04-14": 90}, model="azure/my-deployment", dated=False
    ) is None


@pytest.mark.parametrize("served", ["gpt-4.1-2025-04-14", "GPT-4.1-2025-04-14"])
def test_the_comparison_ignores_case_and_the_provider_prefix(served):
    assert served_model_mismatch({served: 3}, model="openai/gpt-4.1-2025-04-14", dated=True) is None


def test_the_grade_step_checks_it_and_fails_the_arm():
    """The guard is only worth anything if the grade path calls it and stops."""
    import inspect

    from lithrim_bench.cli import loop

    src = inspect.getsource(loop._grade_and_score)
    assert "served_model_mismatch" in src
    assert "SystemExit" in src and "served_model_mismatch" in src
    assert src.index("served_model_mismatch") < src.index('arm["pinned_by"]')
