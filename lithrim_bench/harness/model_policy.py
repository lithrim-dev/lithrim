"""REL-OPS-1 O4 — the dated-model-alias policy (one check at judge BIND time).

SPEC (SPEC_RELIABILITY_PROGRAM.md O4): warn (or refuse, per config) when a judge binds a
FLOATING model alias instead of a dated snapshot; record which was used. An O-item
observes/records/gates — it never touches consensus, so this module sits entirely ABOVE
the frozen seam: ``build_judge_lm``/``build_trio`` (frozen ``judges_dspy.py``) are
untouched. The check runs in ``authored_stage.build_authored_evaluator`` over the
``llm_model`` VOTE-MODEL-1 already stamps on each constructed judge, and the recorded
bindings ride ``plugins.provenance_snapshot()`` → ``PipelineProvenance.model_bindings``
(the TOOL-1/D5 additive-provenance pattern). Stdlib-only, like ``plugins.py``.

Policy default is WARN (env unset → grading byte-identical); refuse mode is opt-in via
``LITHRIM_BENCH_REQUIRE_DATED_MODELS`` (1/true/yes/on). A judge with NO bound LM (the
offline ``predictors=`` path — ``llm_model is None``) is recorded honestly as
``dated: None`` and never warns/refuses: nothing was bound, so there is nothing to pin.
"""

from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)

REQUIRE_DATED_ENV = "LITHRIM_BENCH_REQUIRE_DATED_MODELS"

_TRUTHY = frozenset({"1", "true", "yes", "on"})

# A dated snapshot carries an explicit date-like token: dashed ISO (gpt-4o-2024-08-06)
# or compact YYYYMMDD (claude-3-5-sonnet-20241022), anywhere in the id (a suffix segment
# like ``-20251001-eu2`` still counts). Digit-boundary guards keep long non-date digit
# runs (context sizes, param counts) from matching. Years pinned to 20xx on purpose —
# model snapshots are, and it keeps ``-32k``/``-70b``-adjacent numerics out.
_DATE_TOKEN = re.compile(
    r"(?<!\d)20\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(?!\d)"
    r"|(?<!\d)20\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)"
)

# The registry the provenance snapshot reads: the LAST checked binding set (one council
# construction = one binding set; a rebuild replaces it). ``None`` until a check runs, so
# provenance can distinguish "no council bound" from "bound with zero roles".
_LAST_BINDINGS: list[dict] | None = None


def is_dated_model_id(model_id: str) -> bool:
    """True iff ``model_id`` pins a dated snapshot. ``-latest``/``:latest`` is explicitly
    floating even when a date token appears elsewhere; a bare alias is floating."""
    mid = (model_id or "").strip().lower()
    if not mid or mid.endswith("-latest") or mid.endswith(":latest"):
        return False
    return _DATE_TOKEN.search(mid) is not None


def check_model_bindings(
    bindings: dict[str, str | None], *, env: dict[str, str] | None = None
) -> list[dict]:
    """The O4 bind-time check: classify each role's resolved model id, RECORD every
    binding (``{role, model, dated}``; ``dated: None`` when no LM was bound), then WARN
    on each floating binding — or, under ``LITHRIM_BENCH_REQUIRE_DATED_MODELS``, raise a
    ``ValueError`` naming every offending role + alias. Returns the recorded list."""
    global _LAST_BINDINGS
    records = [
        {
            "role": role,
            "model": model,
            "dated": is_dated_model_id(model) if model else None,
        }
        for role, model in bindings.items()
    ]
    _LAST_BINDINGS = records
    floating = [r for r in records if r["dated"] is False]
    if floating:
        offenders = ", ".join(f"{r['role']}={r['model']!r}" for r in floating)
        refuse = (env if env is not None else os.environ).get(
            REQUIRE_DATED_ENV, ""
        ).strip().lower() in _TRUTHY
        if refuse:
            raise ValueError(
                f"O4 dated-model-alias policy ({REQUIRE_DATED_ENV} is set): floating "
                f"model alias bound for {offenders}. Bind a dated snapshot "
                f"(e.g. gpt-4o-2024-08-06 / claude-3-5-sonnet-20241022), or unset "
                f"{REQUIRE_DATED_ENV} to downgrade to a warning."
            )
        for r in floating:
            logger.warning(
                "O4 dated-model-alias policy: role=%r binds FLOATING model alias %r "
                "(no date-like snapshot suffix) — provider drift is untracked; "
                "pin a dated snapshot",
                r["role"],
                r["model"],
            )
    return records


def last_model_bindings() -> list[dict] | None:
    """The most recently checked binding set (for provenance); ``None`` if no check ran."""
    return None if _LAST_BINDINGS is None else [dict(r) for r in _LAST_BINDINGS]


def _reset_model_bindings() -> None:
    """Test hook: clear the registry."""
    global _LAST_BINDINGS
    _LAST_BINDINGS = None
