from repro.archehr.lithrim_feedback import build_review_case, review_values


def test_value_check_is_native_but_never_semantic_proof():
    result = review_values("Delivery takes 12 days.", "The box contains 12 items.")
    assert result["value_membership"]["conforms"] is True
    assert result["value_membership"]["manifest"]["tool"] == "value_grounding"
    assert result["semantic_support"] is None


def test_missing_value_in_prose_is_only_a_lead():
    result = review_values("Delivery takes 12 days.", "Delivery takes 15 days.")
    assert result["value_membership"]["conforms"] is None
    assert result["value_membership"]["evidence"]["missing"] == ["12"]


def test_no_source_or_numbers_is_inconclusive():
    for answer, source in [("Takes 12 days.", ""), ("It arrived.", "It arrived.")]:
        assert review_values(answer, source)["value_membership"]["conforms"] is None


def test_review_case_has_no_fabricated_labels():
    case = build_review_case("1", "2", "It arrived.", "It arrived yesterday.")
    assert case["case_id"] == "archehr-1-answer-2"
    assert case["source_kind"] == "prose"
    assert "expected_safety_flags" not in case
    assert "injection_recipe" not in case
