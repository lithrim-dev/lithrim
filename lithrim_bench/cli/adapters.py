"""Dataset adapters: the only dataset-specific code in the loop, and it lives outside the engine.

An adapter is a Python file (or importable module) that turns a dataset's own files into
eval cases in the pack's shape. The CLI loads it by path or dotted name and calls:

  download(data_dir)                                       optional; fetch the files if absent
  slice_cases(data_dir, *, per_task, split, natural)       -> list[dict] eval cases
  calibration_corpus(data_dir, *, per_task, test_cases)    -> list[dict] optimizer rows

The reference adapter is ``examples/ragtruth/adapter.py``.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ("slice_cases", "calibration_corpus")


def load_adapter(spec: str, *, repo_root: Path = REPO_ROOT) -> ModuleType:
    """Load an adapter from a ``.py`` path (absolute, or relative to the cwd then the repo root)
    or from a dotted module name; fail closed on a module missing the contract."""
    candidates = [Path(spec), repo_root / spec] if spec.endswith(".py") else []
    path = next((p for p in candidates if p.exists()), None)
    if path is not None:
        name = f"lithrim_adapter_{path.stem}"
        module_spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[name] = module
        module_spec.loader.exec_module(module)
    elif spec.endswith(".py"):
        raise FileNotFoundError(
            f"adapter {spec!r} not found (tried {[str(c) for c in candidates]})"
        )
    else:
        module = importlib.import_module(spec)
    missing = [fn for fn in REQUIRED if not callable(getattr(module, fn, None))]
    if missing:
        raise TypeError(f"adapter {spec!r} lacks {missing}; an adapter must define {REQUIRED}")
    return module
