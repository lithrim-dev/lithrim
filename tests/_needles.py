"""Local release-audit needles (REL-5f, final-gate B2).

The name sweeps hunt strings that must never ship in the tracked tree — so the needles
themselves cannot live in the tree in ANY decodable form (a codepoint tuple is just an
encoding, and a labelled assertion next to it tells a reader what it decodes to). The
needles live in an UNTRACKED local file (``.release_needles.json``, gitignored); every
entry is validated against a one-way sha256 integrity pin below before use. On machines
without the file the name sweeps skip with a reason; the pattern-based sweeps (e.g. the
``/Users/<name>`` regex) run everywhere and need no needle at all.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
NEEDLES_PATH = REPO_ROOT / ".release_needles.json"

# One-way sha256 integrity pins for the local file's entries: they validate a locally
# supplied needle and anchor the anti-regression sweep; they disclose nothing.
NEEDLE_PINS = {
    "maintainer_user": "5392158efda3e1ebf5476c635066dfbd70a6e99452ffba1bb7789b066dc413eb",
    "collaborator": "524b30f818bf83fc541d0cb25109686e77c39fbed86bf11da3db0130f49e5e15",
    "facility": "d1289e5a730e1e6790a48093f470913a1a1dd0942518d3fb5aeab2a0d163bbc0",
}

SKIP_REASON = "release-needles file absent; name sweeps run on the maintainer's machine"


def require_needle(key: str) -> str:
    """The validated local needle for ``key`` — or a skip when the local file is absent.
    A PRESENT file with a wrong entry FAILS (integrity pin), never skips."""
    if not NEEDLES_PATH.is_file():
        pytest.skip(SKIP_REASON)
    entry = json.loads(NEEDLES_PATH.read_text()).get(key)
    if entry is None:
        pytest.skip(f"release-needles file has no entry {key!r}; {SKIP_REASON}")
    assert hashlib.sha256(entry.encode("utf-8")).hexdigest() == NEEDLE_PINS[key], (
        f"release-needles entry {key!r} failed its integrity pin (stale local file?)"
    )
    return entry
