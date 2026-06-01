from lithrim_bench.taxonomy import load_taxonomy


def test_snapshot_loads_and_has_known_codes():
    tx = load_taxonomy()
    assert "WRONG_DOSAGE" in tx.known_codes
    assert "MISSING_ALLERGY" in tx.known_codes
    assert tx.tier_of("WRONG_DOSAGE") == "TIER_1"
    assert tx.tier_of("HALLUCINATED_DETAIL") == "TIER_2"


def test_wrong_dosage_has_production_owners():
    # WS-6c (S-BS-30): production_judges is now the ratified v2 trio
    # (risk/policy/faithfulness). behavior_judge no longer runs, so it is no
    # longer a production owner of WRONG_DOSAGE — the pre-v2 assertion
    # ``{behavior_judge, risk_judge} <= owners`` encoded the v1 monoculture.
    # The invariant this guards is unchanged: WRONG_DOSAGE retains a
    # production-resident scoring path (via risk_judge, which owns it and is in
    # the v2 trio). Flags whose owners are ONLY behavior_judge/source_message_judge
    # have no v2 production owner — tracked as seam S-BS-31, not asserted here.
    tx = load_taxonomy()
    owners = tx.production_owners_of("WRONG_DOSAGE")
    assert "risk_judge" in owners
    assert "behavior_judge" not in owners  # v2: behavior_judge is declared-but-not-running


def test_source_message_judge_is_declared_but_not_running():
    tx = load_taxonomy()
    assert "source_message_judge" in tx.declared_but_not_running
    assert "source_message_judge" not in tx.production_judges
