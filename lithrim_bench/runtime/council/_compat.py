"""Observability stubs for the vendored council (salvaged from app/utils; no-ops)."""
from __future__ import annotations

import logging
from typing import Any


class _StructuredLogger:
    def __init__(self, logger: logging.Logger) -> None:
        self._l = logger

    def _emit(self, lvl: int, msg: Any, *a: Any, **k: Any) -> None:
        try:
            self._l.log(lvl, msg if not a else (str(msg) % a))
        except Exception:
            self._l.log(lvl, str(msg))

    def debug(self, m: Any, *a: Any, **k: Any) -> None: self._emit(logging.DEBUG, m, *a, **k)
    def info(self, m: Any, *a: Any, **k: Any) -> None: self._emit(logging.INFO, m, *a, **k)
    def warning(self, m: Any, *a: Any, **k: Any) -> None: self._emit(logging.WARNING, m, *a, **k)
    def error(self, m: Any, *a: Any, **k: Any) -> None: self._emit(logging.ERROR, m, *a, **k)
    def exception(self, m: Any, *a: Any, **k: Any) -> None: self._l.exception(str(m))
    def bind(self, **k: Any) -> _StructuredLogger: return self


def get_structured_logger(name: str, **_ctx: Any) -> _StructuredLogger:
    return _StructuredLogger(logging.getLogger(name))


class _Timer:
    def __init__(self, name: str) -> None: self.name = name
    def stop(self, *a: Any, **k: Any) -> float: return 0.0
    def observe(self, *a: Any, **k: Any) -> None: return None
    def __enter__(self) -> _Timer: return self
    def __exit__(self, *e: Any) -> bool: return False


def start_timer(name: str, *, tags: Any = None, **_ctx: Any) -> _Timer:
    return _Timer(name)


def emit_counter(name: str, value: int = 1, *, tags: Any = None, **_ctx: Any) -> None:
    return None


def emit_timing(name, value=0, *, tags=None, **_ctx):
    return None


def __getattr__(name):
    def _noop(*a, **k):
        return None
    return _noop
