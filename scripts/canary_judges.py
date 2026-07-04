#!/usr/bin/env python3
"""Provider-drift canary CLI — thin wrapper → :func:`lithrim_bench.canary.main` (REL-OPS-1 O1).

Detects a provider silently changing model behavior behind a pinned model
string: re-grades a small frozen golden set through the existing eval_runner
path and diffs verdict-by-verdict against a pinned baseline.

  # mint (pin) the baseline:
  python scripts/canary_judges.py --record \\
      --pack-path data/canary/golden.jsonl --baseline data/canary/baseline.json \\
      --backend lithrim-pipeline

  # the scheduled re-grade + diff (exit 1 iff any verdict flipped):
  python scripts/canary_judges.py \\
      --pack-path data/canary/golden.jsonl --baseline data/canary/baseline.json \\
      --backend lithrim-pipeline

  # $0 offline smoke on the seeded mock:
  python scripts/canary_judges.py --record --backend mock --noise-seed 0 \\
      --pack-path out/golden.jsonl --baseline out/baseline.json
  python scripts/canary_judges.py --backend mock --noise-seed 0 \\
      --pack-path out/golden.jsonl --baseline out/baseline.json

Known limitation: response-side provider fingerprints (e.g. OpenAI's
``system_fingerprint``) surface below the frozen ``runtime/council/judges_dspy.py``
seam, which this cut must not touch. The baseline records CONFIGURED model
identifiers only (the backend pin); per-response fingerprint capture into
``PipelineProvenance`` is a follow-up requiring an owner decision on a seam
carve-out.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lithrim_bench.canary import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
