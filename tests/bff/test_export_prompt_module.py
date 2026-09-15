"""EXPORT-MODULE-1: the chat export loads only the module the importer manifest declares.

The export route imported and executed whatever `prompt_module` path the request named, so a
caller could make the service exec an arbitrary .py on its filesystem. The manifest is the
contract: the declared module is the only one that loads, and naming a different one is a 422
that says which module the importer declares."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

pytest.importorskip("fastapi")
import app as bff  # noqa: E402


class _Vocab:
    id = "ragtruth"
    training_prompt_module = "examples/ragtruth/training_prompt.py"


def test_the_declared_module_is_accepted():
    assert bff._resolve_prompt_module(None, _Vocab()) == _Vocab.training_prompt_module
    assert bff._resolve_prompt_module(_Vocab.training_prompt_module, _Vocab()) == _Vocab.training_prompt_module


def test_another_module_is_refused_by_name():
    with pytest.raises(bff.HTTPException) as exc:
        bff._resolve_prompt_module("/etc/anything.py", _Vocab())
    assert exc.value.status_code == 422
    assert "examples/ragtruth/training_prompt.py" in str(exc.value.detail)
    assert "importer" in str(exc.value.detail)


def test_an_importer_declaring_none_is_still_a_clear_422():
    empty = types.SimpleNamespace(id="plain", training_prompt_module=None)
    with pytest.raises(bff.HTTPException) as exc:
        bff._resolve_prompt_module(None, empty)
    assert exc.value.status_code == 422 and "declares none" in str(exc.value.detail)
