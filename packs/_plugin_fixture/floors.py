"""PLUGIN-1 D6 fixture floors — a NET-NEW suppress contract registered purely via the pack
manifest + this module, with ZERO edits to the engine (``harness/grounding.py``).

This is the open/closed proof (A4 / SPEC §Success Metrics): under
``LITHRIM_BENCH_PACK=_plugin_fixture`` the engine's ``grounding.suppress_executors()`` and
``grounding.contract_plugins()`` pick up ``fixture_suppress`` through the SAME PACK-3
``load_pack_floors`` interface the clinical ``record_presence`` uses — the engine never names it.
Mirrors the ``packs/healthcare/floors.py`` registration shape (the module exposes the two
declarative dicts ``SUPPRESS_EXECUTORS`` / ``FLOOR_EXECUTORS``)."""

from __future__ import annotations

from typing import Any


class FixtureSuppress:
    """A trivial suppress contract — it only needs to REGISTER (appear in the merged registry)
    for the open/closed proof; ``check`` is never exercised by the D6 tests. Constructed by the
    engine as ``factory(decl)`` (it is not in ``_HTTP_CONTRACT_TYPES``)."""

    def __init__(self, decl: Any) -> None:
        self.flag_code = getattr(decl, "flag_code", "")
        self.question = getattr(decl, "question", "")
        self.version = getattr(decl, "version", "0")

    def check(self, finding: dict[str, Any], case: dict[str, Any]) -> Any:
        from lithrim_bench.harness.grounding import Verdict

        return Verdict(disproved=False, reason="fixture suppress — never disproves")


SUPPRESS_EXECUTORS = {"fixture_suppress": FixtureSuppress}
FLOOR_EXECUTORS: dict[str, Any] = {}
# S-BS-133: declare fixture_suppress as a SERVICE-transport contract so the test can prove a pack's
# service floor is tagged ``transport=service`` in ``contract_plugins()``. The executor itself still
# runs in-process — the manifest ``transport`` is declarative metadata (dispatch is gated by
# ``grounding._HTTP_CONTRACT_TYPES``, unchanged). A real pack with a service-backed floor sets this.
SERVICE_CONTRACT_TYPES = {"fixture_suppress"}
