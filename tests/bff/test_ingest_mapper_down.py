"""Ingest front door: an unreachable JUTE mapper must surface an HONEST, actionable 422 —
"the mapper is not reachable at <url>, start it or set LITHRIM_JUTE_URL" — never a bare 500
and never the misleading "extractor did not converge" diagnosis (the host-path `make up`
stack does not start :3031, so this is the FIRST error a non-Docker user hits).

$0/offline: the client is a fake whose `health()` reports unreachable; no network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lithrim_bench.harness.audit import Actor

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402

_CSV = "case_id,note,dialogue\nc1,a note,a dialogue\n"


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


class _DownJute:
    """Constructable, but the mapper behind it is unreachable."""

    def __init__(self, *_a, **_k):
        self.base = "http://localhost:3031"

    def health(self) -> bool:
        return False


def test_ingest_preview_names_the_down_mapper_not_convergence(tmp_path, monkeypatch):
    monkeypatch.setattr("lithrim_bench.verification.EtlpJuteClient", _DownJute)
    ctx = _real_ctx(tmp_path)
    with pytest.raises(RuntimeError) as exc_info:
        ctx.ingest_preview(raw=_CSV, fmt="csv", filename="cases.csv", agent="ws0_default")
    msg = str(exc_info.value)
    assert "mapper" in msg and "LITHRIM_JUTE_URL" in msg, msg
    assert "converge" not in msg, f"misdiagnosis leaked: {msg}"


def test_real_client_health_is_false_when_unreachable():
    """The REAL client's probe never raises — it answers False on a dead endpoint."""
    from lithrim_bench.verification import EtlpJuteClient

    client = EtlpJuteClient(base_url="http://127.0.0.1:1", timeout=0.2)
    assert client.health() is False
