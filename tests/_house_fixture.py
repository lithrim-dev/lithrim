"""The single chokepoint for the NEUTRAL `_core` house fixture (S-BS-137).

The ~18 PLUMBING tests (run-id / verdict round-trip / audit-shape / suppression-wired)
used to each redefine ``CASE_ID = "bench_scribe_v1_..."`` / ``FIXTURES = .../ws0`` /
``ONTOLOGY_SEED = packs/healthcare/ontology.json`` — three hardcoded clinical paths that
the PACK-DIST-1 extraction removed from CE. They now import the house fixture from HERE,
so the clinical→neutral swap lives in one place and the plumbing runs on the neutral
``_core`` pack in a bare CE checkout (and identically in dev).

The fixture is the proven ``tests/fixtures/standalone`` content-review pattern: a
domain-neutral case whose captured baseline carries ONE standing finding
(``FABRICATED_CLAIM`` → reject) and ONE suppressible finding (``UNSUPPORTED_ASSERTION``,
cleared by the generic ``presence_check``), so ``grounded_adjustments`` is non-empty.
See ``tests/fixtures/_core/README.md``.

Genuinely-clinical funcs (authored-assignment grades, ``domain=='clinical'``,
``flags==23``, the FABRICATED_HISTORY demo-pair flip) do NOT use this chokepoint — they
keep reading the clinical fixture (relocated with the pack in PACK-DIST-2 D5).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lithrim_bench.harness import pack as _pack
from lithrim_bench.harness.config import Agent, Dataset, EvalProfile

_REPO_ROOT = Path(__file__).resolve().parent.parent


def pack_ws0_dir_or_none() -> Path | None:
    """The clinical ``ws0`` house fixture dir resolved from the discoverable healthcare pack
    (``../lithrim-pack-healthcare/fixtures/ws0/``), or ``None`` in a bare CE checkout where the
    pack is nowhere — PACK-DIST-2 C2. Non-skipping: for callers that only need to CONSTRUCT a
    path string (e.g. an Agent the actual ws0 READ never happens for in bare CE because the
    reading func is NEEDS_PACK-skipped). The CE tree carries no clinical fixture; ``ws0`` lives
    one level above the pack root (``_pack_root('healthcare').parent``)."""
    try:
        return _pack._pack_root("healthcare").parent / "fixtures" / "ws0"
    except FileNotFoundError:
        return None


def pack_ws0_dir() -> Path:
    """The clinical ``ws0`` house fixture, resolved from the discoverable healthcare pack
    (``../lithrim-pack-healthcare/fixtures/ws0/``) — PACK-DIST-2 C2.

    For callers that READ the fixture. Every such CE consumer is a ``NEEDS_PACK`` func (it
    grades/replays THROUGH healthcare), so a bare CE checkout has nothing to resolve — this
    ``pytest.skip``s instead of dangling on a gone in-repo path. Dev/CI (pack discoverable)
    resolves the real fixture dir."""
    resolved = pack_ws0_dir_or_none()
    if resolved is None:
        pytest.skip(
            "PACK-DIST-1: healthcare pack not discoverable (bare CE checkout) — the ws0 "
            "house fixture lives with the pack; set LITHRIM_BENCH_PACKS_DIR or install "
            "lithrim-pack-healthcare"
        )
    return resolved

HOUSE_CASE_ID = "_core_house_v1"
HOUSE_FIXTURES_DIR = _REPO_ROOT / "tests" / "fixtures" / "_core"
HOUSE_CASE_PATH = HOUSE_FIXTURES_DIR / "case._core_house.jsonl"
HOUSE_BASELINE_PATH = HOUSE_FIXTURES_DIR / "baseline._core_house.json"
HOUSE_ONTOLOGY_PATH = HOUSE_FIXTURES_DIR / "ontology._core_house.json"
# the fixed provenance id baked into baseline._core_house.json (replay reuses it).
HOUSE_RUN_ID = "c0fe1a2b-3d4e-5f60-7a81-92b3c4d5e6f7"


def house_agent(name: str = "house_test", **overrides: Any) -> Agent:
    """A neutral fixture-pointing Agent over the ``_core`` house fixture (absolute paths
    → hermetic). The shape mirrors the former clinical ``_fixture_agent`` (the v2 trio +
    presence_check tool + a compose-over-live disposition) so the plumbing tests need no
    other change. ``overrides`` patch the assembled ``Agent`` fields (e.g. ``name=``)."""
    agent = Agent(
        name=name,
        eval_profile=EvalProfile(
            judges=("risk_judge", "policy_judge", "faithfulness_judge"),
            council_config={"disposition": "compose-over-live-v2"},
            ontology_ref="_core_house/1",
            ontology_path=str(HOUSE_ONTOLOGY_PATH),
            tools=("presence_check",),
            kb_bindings={},
            severity_map_ref="ontology:_core_house/1",
        ),
        dataset=Dataset(
            case_id=HOUSE_CASE_ID,
            source=str(HOUSE_CASE_PATH),
            baseline=str(HOUSE_BASELINE_PATH),
        ),
    )
    if overrides:
        agent = agent.model_copy(update=overrides)
    return agent
