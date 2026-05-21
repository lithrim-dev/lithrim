from lithrim_bench.taxonomy import load_taxonomy


def test_snapshot_loads_and_has_known_codes():
    tx = load_taxonomy()
    assert "WRONG_DOSAGE" in tx.known_codes
    assert "MISSING_ALLERGY" in tx.known_codes
    assert tx.tier_of("WRONG_DOSAGE") == "TIER_1"
    assert tx.tier_of("HALLUCINATED_DETAIL") == "TIER_2"


def test_wrong_dosage_has_production_owners():
    tx = load_taxonomy()
    owners = tx.production_owners_of("WRONG_DOSAGE")
    assert {"behavior_judge", "risk_judge"} <= owners


def test_source_message_judge_is_declared_but_not_running():
    tx = load_taxonomy()
    assert "source_message_judge" in tx.declared_but_not_running
    assert "source_message_judge" not in tx.production_judges
