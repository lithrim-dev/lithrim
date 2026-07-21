"""CACHE-TRAP-2: the process-global judge-cache lever.

``LITHRIM_JUDGE_CACHE=0`` used to reach only the per-LM ``cache=`` kwarg (CACHE-TRAP-1). dspy
also keeps its OWN process-global disk and memory caches, which serve hits regardless of what
the LM says, so a live grade could complete with zero model calls and report normal success. A
full 14-case arm was captured that way on 2026-07-21, at roughly 2s per case and
``cost_tokens.total == 0``; only a container restart cleared it.

This lives in ``harness`` rather than beside ``build_judge_lm`` on purpose:
``runtime/council/judges_dspy.py`` is byte-frozen at its top-level symbol set (the moat guard,
``tests/_seam_freeze.py``), so a new top-level function there is a freeze violation. Editing
``build_judge_lm``'s BODY is authorized, so it imports and calls this instead.
"""

from __future__ import annotations


def set_global_judge_cache(enabled: bool) -> None:
    """Flip dspy's process-global disk + memory caches.

    The caller restores it: the BFF's live grade re-enables in its ``finally``, mirroring how it
    restores the env var, so a later $0/replay grade in the same process still gets its cache.

    Degrades silently on a dspy without ``configure_cache`` (older releases). A missing lever
    must never detonate a grade; the ``cache_replay`` flag on the record is the backstop that
    keeps a replayed number from being quoted unknowingly.
    """
    import dspy

    configure = getattr(dspy, "configure_cache", None)
    if configure is None:
        return
    configure(enable_disk_cache=enabled, enable_memory_cache=enabled)
