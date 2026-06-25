"""JUTE-ADDON-1 — the regression that the live Docker failure needed: ``_ingest_cases`` constructs
the JUTE client with the RESOLVED base URL, not a hardcoded ``localhost:3031`` default.

In Docker ``localhost:3031`` resolves to the BFF container itself, so the existing DSPy JUTE-gen
ingest can't reach a mapper the user runs on the host / as a compose service / remotely → ingest
fails. The fix threads ``_jute_base_url()`` (env ``LITHRIM_JUTE_URL`` → the manifest default) into
``EtlpJuteClient(base_url=...)``. This test spies on the constructor and asserts the threaded URL.

MUTATION (the named RED): revert to ``EtlpJuteClient()`` → the override assertion goes red (the spy
sees the manifest default, not the override).

$0/offline: the LM/:3031/StoryWorld surface is mocked exactly like ``test_ingest_newsource.py``;
no network, bare-CE.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from lithrim_bench.harness.audit import Actor

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

GH_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "narrative" / "github_newsource_sample.json"

_OVERRIDE = "http://jute-host:9999"
_MANIFEST_DEFAULT = "http://localhost:3031"


@pytest.fixture
def github_dump() -> str:
    return GH_FIXTURE.read_text()


def _real_ctx(tmp_path: Path):
    return bff._build_tool_context(
        req_agent="ws0_default",
        db_path=tmp_path / "config.sqlite",
        out_dir=tmp_path / "out",
        workdir=tmp_path,
        collections_db=tmp_path / "collections.sqlite",
        actor=Actor(type="system", id="test"),
        x_actor=None,
    )


def _github_records(dump: dict) -> list[dict]:
    issues = {i["number"]: i for i in dump["issues"]}
    out: list[dict] = []
    for cm in dump["comments"]:
        issue = issues.get(cm["issue_number"]) or {}
        out.append(
            {
                "case_id": f"gh-{cm['id']}",
                "issue_number": cm["issue_number"],
                "scene_title": issue.get("title"),
                "source": "github",
                "response": cm["body"],
            }
        )
    return out


def _to_github_envelope(records: list[dict]) -> list[dict]:
    from lithrim_bench.verification.jute_extractor import _to_envelope

    return [_to_envelope(r) for r in records]


def _spy_verification_surface(monkeypatch, seen: dict):
    """Mock the verification surface $0/offline AND capture the base_url the JUTE client is
    constructed with. The spy ``FakeJute`` records ``base_url`` into ``seen`` — the assertion
    that proves the url is THREADED, not hardcoded."""

    def fake_bon(make_gen, rules, sample, n=3):
        return SimpleNamespace(accepted=True, jute_transform="t")

    def fake_score(client, template, sample, expected_count=1, required_fields=()):
        records = _github_records(json.loads(sample) if isinstance(sample, str) else sample)
        produced = len(records)
        return {
            "accepted": produced == expected_count,
            "count": produced,
            "expected_count": expected_count,
            "nulls": 0,
            "cases": _to_github_envelope(records),
        }

    class FakeJute:
        def __init__(self, base_url="http://localhost:3031", **_k):
            seen["base_url"] = base_url

        def get_dsl_spec(self):
            return {}

        def persist_or_update(self, *_a, **_k):
            return {"id": 888}

    monkeypatch.setattr("lithrim_bench.verification.best_of_n_extractor", fake_bon)
    monkeypatch.setattr("lithrim_bench.verification.score_extraction", fake_score)
    monkeypatch.setattr("lithrim_bench.verification.render_dsl_excerpt", lambda *a, **k: "")
    monkeypatch.setattr("lithrim_bench.verification.EtlpJuteClient", FakeJute)


def _patch_workspace(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "lithrim_bench.harness.workspace.get_active_workspace",
        lambda: SimpleNamespace(out_dir=tmp_path / "wsout"),
    )


# --------------------------------------------------------------------------- #
# THE regression: the override env is threaded into the client construction.
# --------------------------------------------------------------------------- #
def test_ingest_threads_env_override_into_jute_client(tmp_path, monkeypatch, github_dump):
    """RED at parent (``EtlpJuteClient()``): the spy sees the manifest default, not the override.
    GREEN: ``LITHRIM_JUTE_URL`` is threaded into ``EtlpJuteClient(base_url=...)`` — the spy sees
    the override, so a Docker mapper at a non-localhost URL is now reachable."""
    monkeypatch.setenv("LITHRIM_JUTE_URL", _OVERRIDE)
    seen: dict = {}
    _spy_verification_surface(monkeypatch, seen)
    _patch_workspace(monkeypatch, tmp_path)
    ctx = _real_ctx(tmp_path)

    out = ctx.ingest_cases(
        json_dump=github_dump,
        extraction_rules="one case per `comments`",
        expected_count=6,
    )
    assert out["count"] == 6
    assert seen["base_url"] == _OVERRIDE


def test_ingest_unset_env_is_localhost_byte_compat(tmp_path, monkeypatch, github_dump):
    """Byte-compat: with ``LITHRIM_JUTE_URL`` unset, the client is constructed with the manifest
    default ``localhost:3031`` — identical to today."""
    monkeypatch.delenv("LITHRIM_JUTE_URL", raising=False)
    seen: dict = {}
    _spy_verification_surface(monkeypatch, seen)
    _patch_workspace(monkeypatch, tmp_path)
    ctx = _real_ctx(tmp_path)

    ctx.ingest_cases(
        json_dump=github_dump,
        extraction_rules="one case per `comments`",
        expected_count=6,
    )
    assert seen["base_url"] == _MANIFEST_DEFAULT
