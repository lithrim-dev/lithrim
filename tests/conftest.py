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

PACK-DIST-1: pin healthcare ONLY when it is actually discoverable (in-repo, ``LITHRIM_BENCH_PACKS_DIR``,
or installed). The clinical realm now lives in the external ``lithrim-pack-healthcare`` repo; in a
bare CE checkout (healthcare nowhere) pinning it would FileNotFoundError at the first pack-path
import, so we leave the neutral ``_core`` default and the clinical suite skips-when-absent (the
ROOT ``conftest.py`` carries the skip demarcation for the whole suite).
"""

import os

from lithrim_bench.harness import pack as _pack

try:
    _pack._pack_root("healthcare")
    os.environ.setdefault("LITHRIM_BENCH_PACK", "healthcare")
except FileNotFoundError:
    pass  # bare CE — stay on the neutral _core default; clinical tests skip-when-absent
