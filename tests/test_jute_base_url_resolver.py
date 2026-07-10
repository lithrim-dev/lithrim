"""JUTE-ADDON-1 — the JUTE mapper (:3031) URL is a single configurable add-on setting.

The mapper is an OPT-IN add-on (a separate ../etlp-mapper service), so its base URL must be
env-configurable (``LITHRIM_JUTE_URL``) rather than hardcoded to ``localhost:3031`` via a client
default. In Docker ``localhost`` resolves to the BFF container, so a host/compose/remote mapper is
unreachable without this knob. The default still lives in ONE place — the ``etlp_jute`` plugin
manifest — so back-compat is byte-identical when the env is unset.

Offline + bare-CE: nothing here touches :3031 or the network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

import app as bff  # noqa: E402

from lithrim_bench.backends.etlp_structural import EtlpStructuralBackend  # noqa: E402
from lithrim_bench.harness import plugins  # noqa: E402

_MANIFEST_DEFAULT = "http://localhost:3031"
_SENTINEL = "http://jute-host:9999"


# --------------------------------------------------------------------------- #
# The manifest is the single source of the default.
# --------------------------------------------------------------------------- #
def test_manifest_default_base_url_is_localhost_3031():
    """The ``etlp_jute`` plugin manifest carries the default base URL — the ONE place the default
    lives. The resolver falls back to it; if this changes, the resolver default follows."""
    assert plugins.etlp_jute_default_base_url() == _MANIFEST_DEFAULT


# --------------------------------------------------------------------------- #
# _jute_base_url() — env override wins; unset falls back to the manifest default (byte-compat).
# --------------------------------------------------------------------------- #
def test_jute_base_url_unset_is_manifest_default(monkeypatch):
    """Byte-compat: with ``LITHRIM_JUTE_URL`` unset, the resolver returns the manifest default —
    identical to today's hardcoded ``localhost:3031``."""
    monkeypatch.delenv("LITHRIM_JUTE_URL", raising=False)
    assert bff._jute_base_url() == _MANIFEST_DEFAULT


def test_jute_base_url_env_override_wins(monkeypatch):
    """Non-vacuous: a set ``LITHRIM_JUTE_URL`` is returned verbatim (the add-on URL the user runs
    the mapper at — host.docker.internal / a compose ``jute`` service / a remote)."""
    monkeypatch.setenv("LITHRIM_JUTE_URL", _SENTINEL)
    assert bff._jute_base_url() == _SENTINEL


def test_jute_base_url_read_at_call_time(monkeypatch):
    """No import-time capture: changing the env between calls changes the result."""
    monkeypatch.setenv("LITHRIM_JUTE_URL", _SENTINEL)
    assert bff._jute_base_url() == _SENTINEL
    monkeypatch.delenv("LITHRIM_JUTE_URL", raising=False)
    assert bff._jute_base_url() == _MANIFEST_DEFAULT


# --------------------------------------------------------------------------- #
# EtlpStructuralBackend default base_url honors the env override (explicit-arg path intact).
# --------------------------------------------------------------------------- #
def test_structural_backend_default_unset_is_localhost(monkeypatch):
    """Byte-compat: unset env → the structural backend defaults to ``localhost:3031`` exactly as
    before."""
    monkeypatch.delenv("LITHRIM_JUTE_URL", raising=False)
    assert EtlpStructuralBackend().base_url == _MANIFEST_DEFAULT


def test_structural_backend_default_honors_env(monkeypatch):
    """A set ``LITHRIM_JUTE_URL`` becomes the backend's default base URL (no explicit arg)."""
    monkeypatch.setenv("LITHRIM_JUTE_URL", _SENTINEL)
    assert EtlpStructuralBackend().base_url == _SENTINEL


def test_structural_backend_explicit_arg_overrides_env(monkeypatch):
    """The explicit-arg path is intact: an explicit ``base_url`` wins over the env override."""
    monkeypatch.setenv("LITHRIM_JUTE_URL", _SENTINEL)
    assert EtlpStructuralBackend(base_url="http://explicit:1234").base_url == "http://explicit:1234"
