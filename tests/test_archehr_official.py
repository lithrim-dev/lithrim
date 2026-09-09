import json
import os
from pathlib import Path

import pytest

from repro.archehr.official import score_official


def test_unknown_scorer_refused_before_execution(tmp_path):
    scorer = tmp_path / "scorer.py"
    scorer.write_text("raise RuntimeError('must not execute')")
    with pytest.raises(ValueError, match="scorer hash"):
        score_official(
            scorer_path=scorer,
            inputs_path=tmp_path / "missing.json",
            submission_path=tmp_path / "missing.json",
            key_path=tmp_path / "key.json",
            output_dir=tmp_path / "score",
        )
    assert not (tmp_path / "score").exists()


def test_real_pinned_scorer_on_synthetic_fixture(tmp_path):
    location = os.environ.get("ARCHEHR_SCORER_PATH")
    if not location:
        pytest.skip("Set ARCHEHR_SCORER_PATH for optional pinned-upstream integration test")
    fixtures = Path(__file__).resolve().parents[1] / "repro/archehr/fixtures"
    args = {
        "scorer_path": Path(location),
        "inputs_path": fixtures / "inputs.json",
        "submission_path": fixtures / "prediction.json",
        "key_path": fixtures / "key.json",
        "output_dir": tmp_path / "score",
    }
    report = score_official(**args)
    assert report["score_kind"] == "synthetic_plumbing_not_benchmark"
    assert report["scores"]["overall_score"] == 0.0
    assert report["leaderboard_submission"] is False
    with pytest.raises(FileExistsError):
        score_official(**args)
    key = json.loads((fixtures / "key.json").read_text())
    key.append(key[0])
    bad = tmp_path / "bad_key.json"
    bad.write_text(json.dumps(key))
    with pytest.raises(ValueError, match="duplicate"):
        score_official(**{**args, "key_path": bad, "output_dir": tmp_path / "bad"})
