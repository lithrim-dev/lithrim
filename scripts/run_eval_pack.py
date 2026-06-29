#!/usr/bin/env python3
"""Thin CLI wrapper → :func:`lithrim_bench.harness.pack_gate.main` (DOGFOOD-1 D4).

The CI/CD eval-pack gate. Also exposed as the ``lithrim-pack`` console script.

  # gate a pre-built frozen pack (offline, $0):
  python scripts/run_eval_pack.py --pack out/pack_all_azure.json

  # build a pack from the imported cases under a judge set, then gate it (PAID in_process):
  python scripts/run_eval_pack.py --build --judge-set all_azure --in-process \
      --dump out/pack_all_azure.json
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.harness.pack_gate import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
