"""INGEST-LIMIT-1: an oversized paste/upload is refused with a number, not an opaque failure.

/v1/ingest/preview and /commit read the whole blob into memory and hand it to the mapper. A
multi-hundred-megabyte paste (someone's whole trace export) took the service down or died deep
inside the decoder with a message nobody could act on. The front door states its limit and names
what arrived, and the limit is settable (LITHRIM_INGEST_MAX_MB) for a bigger box."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402


def test_the_default_limit_is_stated_in_megabytes():
    assert bff._ingest_max_bytes() == 64 * 1024 * 1024


def test_the_limit_is_settable(monkeypatch):
    monkeypatch.setenv("LITHRIM_INGEST_MAX_MB", "2")
    assert bff._ingest_max_bytes() == 2 * 1024 * 1024


def test_a_blob_under_the_limit_passes(monkeypatch):
    monkeypatch.setenv("LITHRIM_INGEST_MAX_MB", "1")
    bff._refuse_oversized_ingest("x" * 1000)  # no raise


def test_an_oversized_blob_is_a_422_naming_both_sizes(monkeypatch):
    monkeypatch.setenv("LITHRIM_INGEST_MAX_MB", "1")
    with pytest.raises(bff.HTTPException) as exc:
        bff._refuse_oversized_ingest("x" * (2 * 1024 * 1024))
    assert exc.value.status_code == 422
    detail = str(exc.value.detail)
    assert "2.0 MB" in detail and "1 MB" in detail
    assert "LITHRIM_INGEST_MAX_MB" in detail, "the message says how to raise it"


def test_both_ingest_routes_check_it():
    import inspect

    for fn in (bff.ingest_preview_endpoint, bff.ingest_commit_endpoint):
        assert "_refuse_oversized_ingest" in inspect.getsource(fn), fn.__name__
