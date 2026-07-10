"""NARR-5-CRIT — the sanctioned gradeable-criterion snapshot writer.

The FIRST audited writer above the CLAUDE.md "never hand-edit the snapshot / read-only at
grade time" invariant (``docs/specs/SPEC_CLINICAL_SCRIBE_SELF_SERVE.md`` NARR-5-CRIT, owner
sign-off 2026-06-21). It does NOT weaken the labels-true-by-construction gate — it is the
*admissible* self-serve path INTO it: it splices a new gradeable code into the ACTIVE pack's
taxonomy snapshot (``tiers`` + ``lenses`` + ``tier1_owners``-when-T1) so the existing
admissibility gate (``harness.admissibility.gradeable_flags_outside_snapshot``) then passes
for that code, and the owner judge may raise it (the snapshot ``lenses`` is the withstands-gate
scope authority).

Gated to **tier:core** packs: a ``tier:pro`` pack's snapshot is a lithrim-backend re-snapshot
(``scripts/snapshot_taxonomy.py``), NOT self-authored — splicing one would desync the
contract-of-record. Config-plane write ONLY — the moat/council is untouched ("no engine edit").

The BFF (``apps/bff/app.py`` ``POST /v1/criterion``) calls :func:`splice_gradeable_criterion`,
then appends the ``gradeable=True`` ontology flag (overlay) under the now-passing lint, in ONE
audited action; on an ontology failure it calls :func:`restore_snapshot` to keep the two atomic.
"""

from __future__ import annotations

import copy
import json
import os
import re
import tempfile
from pathlib import Path

from . import pack as _pack

# A taxonomy code is an uppercase-led SCREAMING_SNAKE token (matches every shipped snapshot code).
# The contract-of-record writer refuses anything else BEFORE it can land in tiers/lenses (F1).
_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# the council tier-set names (the snapshot ``tiers`` keys) ↔ the ontology-flag short form
_LONG_TO_SHORT = {
    "TIER_1_NEVER_EVENTS": "TIER_1",
    "TIER_2_HIGH_RISK": "TIER_2",
    "TIER_3_MEDIUM": "TIER_3",
}
# every accepted SME-facing alias → the canonical snapshot tier-set name (long)
_TIER_ALIASES = {
    "TIER_1": "TIER_1_NEVER_EVENTS",
    "T1": "TIER_1_NEVER_EVENTS",
    "TIER_2": "TIER_2_HIGH_RISK",
    "T2": "TIER_2_HIGH_RISK",
    "TIER_3": "TIER_3_MEDIUM",
    "T3": "TIER_3_MEDIUM",
    **{long: long for long in _LONG_TO_SHORT},
}


class CriterionError(Exception):
    """Base for the self-serve gradeable-criterion authoring rejections (BFF → 422/409)."""


class NonCorePackError(CriterionError):
    """The active pack is not tier:core (its snapshot is a backend re-snapshot). → 422"""


class UnknownOwnerError(CriterionError):
    """owner_role is not a production judge of the pack. → 422"""


class BadTierError(CriterionError):
    """tier is not one of TIER_1|2|3 (or an accepted alias). → 422"""


class DuplicateCriterionError(CriterionError):
    """code already exists in the pack's taxonomy. → 409"""


class BadCodeError(CriterionError):
    """code is empty / malformed (not an uppercase-led SCREAMING_SNAKE token). → 422"""


def resolve_tier_name(tier: str) -> str:
    """SME-facing tier (``TIER_2`` / ``T2`` / ``TIER_2_HIGH_RISK``) → the snapshot tier-set name."""
    name = _TIER_ALIASES.get(tier)
    if name is None:
        raise BadTierError(f"unknown tier {tier!r}; expected one of {sorted(set(_TIER_ALIASES))}")
    return name


def short_tier_name(tier: str) -> str:
    """SME-facing tier → the ontology-flag short form (``TIER_2``)."""
    return _LONG_TO_SHORT[resolve_tier_name(tier)]


def splice_gradeable_criterion(pack: str, code: str, tier: str, owner_role: str) -> tuple[dict, dict]:
    """Splice a new gradeable CODE into PACK's snapshot, write it back, clear the council
    known-codes cache, and return ``(before, after)`` for the audit.

    Splices: ``tiers[<tier-set>]`` += code (the gradeable gate union); ``lenses[owner_role]`` +=
    code (the withstands-gate scope authority — the owner may raise it); and, for a Tier-1
    criterion, ``tier1_owners[code] = [owner_role]`` (the consensus one-strike owner-map).

    Raises (the BFF maps to HTTP): :class:`NonCorePackError` / :class:`BadTierError` /
    :class:`UnknownOwnerError` (422), :class:`DuplicateCriterionError` (409). Validation runs
    BEFORE any write — a rejected request never touches the snapshot file.
    """
    if _pack._manifest(pack).get("tier", "core") != "core":
        raise NonCorePackError(
            f"pack {pack!r} is not tier:core; a tier:pro pack's taxonomy snapshot is a "
            "lithrim-backend re-snapshot (scripts/snapshot_taxonomy.py), not self-authored"
        )
    if not isinstance(code, str) or not _CODE_RE.match(code):
        raise BadCodeError(
            f"code {code!r} is malformed; a taxonomy code must be an uppercase-led "
            "SCREAMING_SNAKE token (^[A-Z][A-Z0-9_]*$)"
        )
    tier_name = resolve_tier_name(tier)
    production = _pack.pack_production_judges(pack)
    if owner_role not in production:
        raise UnknownOwnerError(
            f"owner_role {owner_role!r} is not a production judge of pack {pack!r} "
            f"(production_judges={production})"
        )
    if code in _pack.pack_taxonomy_codes(pack):
        raise DuplicateCriterionError(f"code {code!r} already exists in pack {pack!r} taxonomy")

    snap_path = _pack._pack_ref(pack, "flags_ref")
    before = json.loads(snap_path.read_text())
    after = copy.deepcopy(before)
    after["tiers"][tier_name] = [*after["tiers"][tier_name], code]
    after["lenses"][owner_role] = [*after["lenses"].get(owner_role, []), code]
    if tier_name == "TIER_1_NEVER_EVENTS":
        after.setdefault("tier1_owners", {})[code] = [owner_role]
    _write_snapshot(snap_path, after)
    _pack._council_known_codes.cache_clear()
    return before, after


def _write_snapshot(path: Path, snapshot: dict) -> None:
    """Serialize + atomically write a snapshot. ``ensure_ascii=False``: the snapshots store RAW
    unicode (em-dashes etc.); escaping them would reformat the tracked file on EVERY write -- incl.
    a content-identical rollback (the live A-LIVE NIT) -- so byte-fidelity keeps a no-op restore a
    true no-op. Atomic (temp-in-dir + ``os.replace``) so a concurrent reader never sees a partial
    write (F6)."""
    text = json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_snapshot_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def restore_snapshot(pack: str, snapshot: dict) -> None:
    """Roll the pack snapshot back to ``snapshot`` (the BFF's atomicity backstop: if the ontology
    overlay or audit write fails AFTER a successful splice, undo the splice so the snapshot +
    ontology never diverge). Atomic, byte-faithful write; clears the council known-codes cache."""
    snap_path = _pack._pack_ref(pack, "flags_ref")
    _write_snapshot(snap_path, snapshot)
    _pack._council_known_codes.cache_clear()
