"""Session-scoped pack pin for the EXISTING test suite (CE-PACK-NEUTRAL-DEFAULT, D0).

The shipped core default is the neutral ``_core`` pack (``harness/pack.py`` ``DEFAULT_PACK``),
so the core boots standalone without the healthcare pack on disk. The existing suite, however,
deeply assumes the clinical pack (floors / generators / clinical taxonomy / ``ONTOLOGY_SEED =
packs/healthcare/…`` fixtures), and pack resolution is frozen at module import — so the suite is
pinned back to ``healthcare`` here.

This is set BEFORE any council / pack import so ``active_pack()`` resolves ``healthcare`` for the
whole suite, while the *shipped* default (env unset) is ``_core``. The neutral default is exercised
ONLY by the subprocess proofs that explicitly UNSET ``LITHRIM_BENCH_PACK`` (``tests/test_neutral_default.py``).
``setdefault`` (not assignment) so an explicit ``LITHRIM_BENCH_PACK=…`` on the command line still wins.
"""

import os

os.environ.setdefault("LITHRIM_BENCH_PACK", "healthcare")
