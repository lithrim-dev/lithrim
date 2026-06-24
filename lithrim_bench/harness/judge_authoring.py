"""PHASE2-A — the sanctioned production-judge snapshot writer.

The STRUCTURAL TWIN of :mod:`harness.criterion` (the gradeable-criterion writer, NARR-5-CRIT,
owner sign-off 2026-06-21). This is the SECOND audited writer above the CLAUDE.md "never
hand-edit the snapshot / read-only at grade time" invariant — owner sign-off 2026-06-25, after
the ``docs/research/PROBE_phase2_arbitrary_judges_2026-06-25.md`` §8 gate was discharged (the
FROZEN consensus admits arbitrary judges at N≥2). It is the *admissible* self-serve path INTO
the by-construction invariant: it splices a new production judge into the ACTIVE pack's taxonomy
snapshot — ``production_judges`` (the roster IDENTITY the frozen council iterates), ``lenses``
(the withstands-gate scope authority — the codes the judge may raise), and ``tier1_owners`` (the
consensus one-strike owner-map, for any owned codes) — behind an AUTHOR-TIME by-construction
admissibility gate that is the entire governance promise.

Gated to **tier:core** packs, exactly like :func:`criterion.splice_gradeable_criterion`: a
``tier:pro`` pack's snapshot is a lithrim-backend re-snapshot (``scripts/snapshot_taxonomy.py``),
NOT self-authored — splicing a judge into one would desync the contract-of-record. Config-plane
write ONLY — the moat/council is untouched ("no engine edit"); the frozen council resolves its
runtime roster/lenses/owner-map FROM the spliced snapshot (the PACK-2c/2b inline-``__import__``
carve-outs already make the snapshot the runtime source-of-truth).

The by-construction admissibility gate (ALL author-time, ALL run BEFORE any write — a rejected
request never touches the snapshot file):

1. **tier:core** — else :class:`NonCorePackError`.
2. **role-id well-formed** — a snake/lower judge-id; else :class:`BadRoleIdError`.
3. **no role collision** — the role-id must not already be a ``production_judges`` entry; else
   :class:`RoleCollisionError`.
4. **lens non-empty** — a judge with no lens may raise nothing; else :class:`EmptyLensError`.
5. **codes ∈ the active taxonomy** — every code in ``lens_codes ∪ owned_codes`` ∈ the pack's
   taxonomy codes (the snapshot ``tiers`` union); else :class:`UnknownCodeError`.
6. **owner↔emit** — every ``owned_codes`` ⊆ ``lens_codes`` (no inert owner: an owner must also
   be able to emit the code it owns); else :class:`InertOwnerError`.

The BFF (PHASE2-B, ``POST /v1/judges``) calls :func:`splice_production_judge`, then seeds the
role prompt (:func:`write_role_prompt`), in ONE audited action; on a later failure it calls
:func:`restore_snapshot` to keep the splice + the prompt seed atomic.
"""

from __future__ import annotations

import copy
import json
import re

from . import pack as _pack
from .criterion import _write_snapshot, restore_snapshot  # twin: reuse the atomic write + rollback

__all__ = [
    "JudgeAuthoringError",
    "NonCorePackError",
    "BadRoleIdError",
    "RoleCollisionError",
    "EmptyLensError",
    "UnknownCodeError",
    "InertOwnerError",
    "splice_production_judge",
    "write_role_prompt",
    "restore_snapshot",
]

# A judge role-id is a lowercase-led snake token (matches every shipped production_judges role:
# risk_judge / policy_judge / faithfulness_judge / behavior_judge / source_message_judge). The
# contract-of-record writer refuses anything else BEFORE it can land in production_judges.
_ROLE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class JudgeAuthoringError(Exception):
    """Base for the self-serve production-judge authoring rejections (BFF → 422/409)."""


class NonCorePackError(JudgeAuthoringError):
    """The active pack is not tier:core (its snapshot is a backend re-snapshot). → 422"""


class BadRoleIdError(JudgeAuthoringError):
    """role is empty / malformed (not a lowercase-led snake token). → 422"""


class RoleCollisionError(JudgeAuthoringError):
    """role already exists in the pack's production_judges. → 409"""


class EmptyLensError(JudgeAuthoringError):
    """lens_codes is empty — a judge with no lens may raise nothing. → 422"""


class UnknownCodeError(JudgeAuthoringError):
    """a lens/owned code is not in the pack's taxonomy (tiers union). → 422"""


class InertOwnerError(JudgeAuthoringError):
    """an owned code is not in lens_codes — an owner that cannot emit what it owns. → 422"""


def splice_production_judge(
    pack: str,
    role: str,
    lens_codes: list[str],
    owned_codes: list[str],
) -> tuple[dict, dict]:
    """Splice a new production judge ROLE into PACK's snapshot, write it back, clear the council
    caches the splice invalidates, and return ``(before, after)`` for the audit.

    Splices (on the snapshot dict): ``production_judges`` += ``[role]`` (append — order is
    load-bearing, it IS the roster order); ``lenses[role]`` = ``sorted(lens_codes)`` (the
    withstands-gate scope authority); and, for each ``c`` in ``owned_codes``,
    ``tier1_owners.setdefault(c, []).append(role)`` (the consensus one-strike owner-map).

    Raises (the BFF maps to HTTP), ALL before any write: :class:`NonCorePackError` /
    :class:`BadRoleIdError` / :class:`EmptyLensError` / :class:`UnknownCodeError` /
    :class:`InertOwnerError` (422), :class:`RoleCollisionError` (409). A rejected request never
    touches the snapshot file.
    """
    if _pack._manifest(pack).get("tier", "core") != "core":
        raise NonCorePackError(
            f"pack {pack!r} is not tier:core; a tier:pro pack's taxonomy snapshot is a "
            "lithrim-backend re-snapshot (scripts/snapshot_taxonomy.py), not self-authored"
        )
    if not isinstance(role, str) or not _ROLE_RE.match(role):
        raise BadRoleIdError(
            f"role {role!r} is malformed; a judge role-id must be a lowercase-led snake token "
            "(^[a-z][a-z0-9_]*$)"
        )
    production = _pack.pack_production_judges(pack)
    if role in production:
        raise RoleCollisionError(
            f"role {role!r} already exists in pack {pack!r} production_judges {production}"
        )
    lens = list(lens_codes)
    if not lens:
        raise EmptyLensError(
            f"lens_codes is empty for role {role!r}; a judge with no lens may raise nothing"
        )
    known = _pack.pack_taxonomy_codes(pack)
    unknown = sorted((set(lens) | set(owned_codes)) - known)
    if unknown:
        raise UnknownCodeError(
            f"codes {unknown} are not in pack {pack!r} taxonomy (tiers union); "
            "splice the criterion first (POST /v1/criterion)"
        )
    inert = sorted(set(owned_codes) - set(lens))
    if inert:
        raise InertOwnerError(
            f"owned codes {inert} are not in lens_codes for role {role!r}; "
            "an owner must also be able to emit the code it owns (owner↔emit)"
        )

    snap_path = _pack._pack_ref(pack, "flags_ref")
    before = json.loads(snap_path.read_text())
    after = copy.deepcopy(before)
    after["production_judges"] = [*after["production_judges"], role]
    after["lenses"][role] = sorted(lens)
    for code in owned_codes:
        after.setdefault("tier1_owners", {}).setdefault(code, [])
        after["tier1_owners"][code] = [*after["tier1_owners"][code], role]
    _write_snapshot(snap_path, after)
    _pack._council_known_codes.cache_clear()
    _pack.assert_pack_judges_consistent.cache_clear()
    return before, after


def write_role_prompt(pack: str, role: str, text: str) -> None:
    """Write the role-prompt seed into ``pack_prompts_path(pack)`` ``council_roles/<role>.txt``
    (tier:core only). Satisfies the ``judge_assignment.load_role_prompt`` FileNotFoundError wall —
    a blank/templated seed is fine; refinement rides the ``assignments`` plane. Idempotent
    overwrite (last-write-wins, the authoring loop re-seeds on edit)."""
    if _pack._manifest(pack).get("tier", "core") != "core":
        raise NonCorePackError(
            f"pack {pack!r} is not tier:core; its council_roles are a backend artifact, "
            "not self-authored"
        )
    if not isinstance(role, str) or not _ROLE_RE.match(role):
        raise BadRoleIdError(
            f"role {role!r} is malformed; a judge role-id must be a lowercase-led snake token "
            "(^[a-z][a-z0-9_]*$)"
        )
    prompts_dir = _pack._pack_ref(pack, "council_roles")
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / f"{role}.txt").write_text((text or "").strip() + "\n", encoding="utf-8")
