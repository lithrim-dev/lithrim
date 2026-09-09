"""Acceptance tests for the paper-prompt arm (offline; a fake model call, no network, no keys)."""

import json

import pytest

from repro.ragtruth import paper_prompt_arm as ppa

ROW = {
    "case_id": "ragtruth_1",
    "transcript": '{"name": "A", "attributes": {"WiFi": null}}',
    "artifacts": [{"type": "response", "content": "A has no wifi."}],
    "ragtruth": {"id": "1", "source_id": "s1", "model": "m"},
}


def _cases(tmp_path, rows):
    p = tmp_path / "cases.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def test_prompt_is_the_paper_prompt_with_record_and_overview_substituted():
    p = ppa.build_prompt('{"a": 1}', "an overview")
    assert p.startswith('Below is a structured data in the JSON format:\n{"a": 1}\n')
    assert "\nan overview\n" in p
    assert '"null" or "None" represents an unknown value rather than a negation' in p
    assert p.rstrip().endswith("Output:")
    assert "{business info}" not in p and "{overview}" not in p


@pytest.mark.parametrize(
    "text,valid,spans",
    [
        ('{"hallucination list": ["a", "b"]}', True, ["a", "b"]),
        ('```json\n{"hallucination list": []}\n```', True, []),
        ('Sure. {"hallucination list": ["x"]} Done.', True, ["x"]),
        ("not json at all", False, []),
        ('{"hallucination list": "x"}', False, []),
        ('{"other": []}', False, []),
        # Mistral's shape: items are objects carrying the span under "span"
        (
            '```json\n{"hallucination list": [{"span": "no wifi", "type": "conflict", '
            '"explanation": "e"}]}\n```',
            True,
            ["no wifi"],
        ),
        # two blocks: the last one carrying the key wins (the final answer)
        (
            '```json\n{"hallucination list": ["draft"]}\n```\nOn reflection:\n```json\n'
            '{"hallucination list": []}\n```\n1. **Conflict**: none.',
            True,
            [],
        ),
        ('{"hallucination list": [{"type": "conflict"}]}', False, []),
    ],
)
def test_parse_output_accepts_fenced_or_wrapped_json_and_keeps_malformed_as_invalid(
    text, valid, spans
):
    out = ppa.parse_output(text)
    assert out["valid"] is valid and out["spans"] == spans


def test_response_level_rule():
    assert ppa.response_level({"valid": True, "spans": ["x"]}) == "halu"
    assert ppa.response_level({"valid": True, "spans": []}) == "clean"
    assert ppa.response_level({"valid": False, "spans": []}) == "invalid"


def test_load_cases_refuses_gold_rows(tmp_path):
    gold = dict(ROW, expected_safety_flags=["X"])
    with pytest.raises(ValueError, match="gold"):
        ppa.load_cases(_cases(tmp_path, [gold]))
    cases = ppa.load_cases(_cases(tmp_path, [ROW]))
    assert cases[0]["case_id"] == "ragtruth_1" and cases[0]["response"] == "A has no wifi."


def test_run_is_resumable_retains_failures_and_never_writes_gold(tmp_path):
    cases = ppa.load_cases(_cases(tmp_path, [ROW, dict(ROW, case_id="ragtruth_2")]))
    calls = []

    def call(prompt):
        calls.append(prompt)
        if len(calls) == 2:
            raise RuntimeError("boom")
        return {
            "content": '{"hallucination list": ["no wifi"]}',
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "model": "gpt-x",
            "fingerprint": "fp",
            "temperature_dropped": False,
        }

    rep = ppa.run(
        cases,
        call,
        out_dir=tmp_path / "o",
        model="gpt-x",
        provider="azure",
        endpoint_host="h",
        api_version="v",
        ceiling=10,
    )
    assert rep["ok"] == 1 and rep["errors"] == 1 and len(calls) == 2
    rec = json.loads((tmp_path / "o" / "runs" / "ragtruth_1.json").read_text())
    assert rec["response_level"] == "halu" and rec["usage"]["total_tokens"] == 15
    assert not (ppa.GOLD_KEYS & set(rec))
    failed = json.loads((tmp_path / "o" / "runs" / "ragtruth_2.json").read_text())
    assert failed["error"] and failed["response_level"] == "error"
    rep2 = ppa.run(
        cases,
        call,
        out_dir=tmp_path / "o",
        model="gpt-x",
        provider="azure",
        endpoint_host="h",
        api_version="v",
        ceiling=10,
    )
    assert len(calls) == 2 and rep2["skipped_existing"] == 2


def test_span_overlap_is_pooled_char_overlap():
    rows = [
        {"response": "abc def ghi", "pred": ["abc def"], "gold": [(0, 3)]},
        {"response": "xyz", "pred": [], "gold": [(0, 3)]},
    ]
    s = ppa.span_overlap(rows)
    assert s["pred_chars"] == 7 and s["gold_chars"] == 6 and s["overlap_chars"] == 3
    assert s["precision"] == round(3 / 7, 4) and s["recall"] == 0.5


def test_load_env_from_cmd_parses_key_value_lines(monkeypatch):
    monkeypatch.delenv("PPA_TEST_A", raising=False)
    monkeypatch.delenv("PPA_TEST_B", raising=False)
    names = ppa.load_env_from_cmd("printf 'PPA_TEST_A=1\\n# c\\nPPA_TEST_B=\"two\"\\n\\n'")
    import os

    assert names == ["PPA_TEST_A", "PPA_TEST_B"]
    assert os.environ["PPA_TEST_A"] == "1" and os.environ["PPA_TEST_B"] == "two"


def test_score_response_level_counts_invalid_as_not_detected(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    recs = {
        "ragtruth_1": "halu",
        "ragtruth_2": "clean",
        "ragtruth_3": "invalid",
        "ragtruth_4": "halu",
    }
    raw_for = {
        "halu": '{"hallucination list": ["x"]}',
        "clean": '{"hallucination list": []}',
        "invalid": "no json here",
    }
    for cid, rl in recs.items():
        (runs / f"{cid}.json").write_text(
            json.dumps({"case_id": cid, "response_level": rl, "raw": raw_for[rl]})
        )
    labels = tmp_path / "labels.jsonl"
    rows = []
    for i, (cid, halu) in enumerate(
        {"ragtruth_1": True, "ragtruth_2": False, "ragtruth_3": True, "ragtruth_4": False}.items()
    ):
        rows.append(
            {
                "case_id": cid,
                "expected_safety_flags": ["X"] if halu else [],
                "ragtruth": {"source_id": f"s{i}", "model": "m"},
            }
        )
    labels.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    rep = ppa.score([str(runs)], labels=str(labels))
    assert rep["n"] == 4 and rep["invalid"] == 1
    assert rep["response_level"]["invalid_as_clean"]["precision"] == 0.5
    assert rep["response_level"]["invalid_as_clean"]["recall"] == 0.5
    assert rep["response_level"]["invalid_as_halu"]["recall"] == 1.0


def test_call_sends_a_user_agent_and_one_user_turn_at_temperature_zero(monkeypatch):
    seen = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [{"message": {"content": '{"hallucination list": []}'}}],
                    "usage": {"total_tokens": 3},
                    "model": "m",
                }
            ).encode()

    def fake_urlopen(req, timeout=0):
        seen["url"] = req.full_url
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        seen["body"] = json.loads(req.data.decode())
        return _Resp()

    monkeypatch.setattr(ppa.urllib.request, "urlopen", fake_urlopen)
    call = ppa.make_call("openai_compatible", "https://x/v1/", "M", None, "k")
    out = call("hello")
    assert out["content"] == '{"hallucination list": []}' and out["temperature_dropped"] is False
    assert seen["url"] == "https://x/v1/chat/completions"
    assert seen["headers"]["user-agent"] == ppa.USER_AGENT
    assert seen["headers"]["authorization"] == "Bearer k" and seen["headers"]["api-key"] == "k"
    assert seen["body"] == {
        "messages": [{"role": "user", "content": "hello"}],
        "temperature": 0,
        "model": "M",
    }


def test_openai_compatible_call_appends_api_version_when_given(monkeypatch):
    seen = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"choices": [{"message": {"content": "{}"}}]}'

    def fake_urlopen(req, timeout=0):
        seen["url"] = req.full_url
        return _Resp()

    monkeypatch.setattr(ppa.urllib.request, "urlopen", fake_urlopen)
    ppa.make_call(
        "openai_compatible",
        "https://r.services.ai.azure.com/models",
        "M",
        "2024-05-01-preview",
        "k",
    )("hi")
    assert seen["url"] == (
        "https://r.services.ai.azure.com/models/chat/completions?api-version=2024-05-01-preview"
    )


def test_score_reparses_raw_with_the_current_parser(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    stale = {
        "case_id": "ragtruth_1",
        "response_level": "invalid",
        "parsed": {"valid": False, "spans": []},
        "raw": '{"hallucination list": [{"span": "x"}]}',
    }
    (runs / "ragtruth_1.json").write_text(json.dumps(stale))
    labels = tmp_path / "labels.jsonl"
    labels.write_text(
        json.dumps(
            {
                "case_id": "ragtruth_1",
                "expected_safety_flags": ["X"],
                "ragtruth": {"source_id": "s", "model": "m"},
            }
        )
        + "\n"
    )
    rep = ppa.score([str(runs)], labels=str(labels))
    assert rep["invalid"] == 0 and rep["response_level"]["invalid_as_clean"]["recall"] == 1.0
