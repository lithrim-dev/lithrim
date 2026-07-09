"""The prompt↔ontology bridge — council-light (UAP-2).

Renders a judge's ``role_key_questions`` from its ontology assignment, reading the
committed ``council_roles/<role>.txt`` seed and composing the authored flag lens +
the role's questions on top. Deliberately imports NOTHING from
``compliance_council`` (no ``openai``/``dspy``/``tenacity``): the render is pure
file-IO + duck-typed ontology access, so the BFF can serve the **$0 prompt preview**
(GET /v1/judges/{role}) without the ``[council]`` extra — the A8 demonstrability
("the assignment→prompt link works in any room, zero creds") is strictly true.

``judges_dspy`` re-exports ``load_role_prompt`` / ``render_role_questions`` from
here, so ``build_trio`` and the optimizer keep one import surface; the council layer
adds the heavy bindings (``Judge``/``dspy.LM``) above this module, never below it.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ...harness.pack import pack_prompts_path

# The per-role prompt sources the live prompt-council loads (compliance_council
# ._load_role_prompts globs the same dir → prompts[file.stem]); the DSPy Judge is
# fed the SAME text via role_prompt= so the A/B compares like prompts. PACK-2: the
# prompts relocated INTO the active healthcare pack; both readers resolve via
# pack_prompts_path() (harness.pack is stdlib-only, so the BFF $0 preview keeps
# working without the [council] extra).
_ROLE_PROMPTS_DIR = pack_prompts_path()


def load_role_prompt(role: str, *, prompts_dir: Path | None = None) -> str:
    """Read ``council_roles/<role>.txt`` and return it ``.strip()``ed — the
    byte-identical prompt text the live prompt-council loads via
    ``_load_role_prompts`` (which also ``.strip()``s, ``compliance_council.py:527``;
    the file ``stem`` is the role key). The strip closes S-BS-44: without it the
    DSPy arm fed a trailing-newline-divergent prompt, breaking the A/B's
    like-for-like premise. Raises if the role prompt is missing rather than
    feeding an empty ``role_prompt`` to the signature.

    ``prompts_dir`` (GENERALIST-1): resolve against an EXPLICIT prompts dir instead of the
    import-time ``_ROLE_PROMPTS_DIR`` (which is bound to the boot/default pack). The in-process
    BFF boots on the neutral default pack, so a non-default-pack role's prompt (e.g. a clinverdict
    ``generalist_reviewer``) only resolves when the caller passes that workspace's pack dir
    (``pack_prompts_path(ws.pack)``). ``None`` (the default) keeps the boot-pack behaviour."""
    base = prompts_dir if prompts_dir is not None else _ROLE_PROMPTS_DIR
    path = base / f"{role}.txt"
    if not path.exists():
        raise FileNotFoundError(f"no council role prompt for {role!r} at {path}")
    return path.read_text(encoding="utf-8").strip()


def render_role_questions(
    ontology: Any,
    role: str,
    *,
    assigned_flags: Sequence[str] | None = None,
    prompts_dir: Path | None = None,
) -> str:
    """Render a judge's ``role_key_questions`` from its ontology assignment (UAP-2).

    The prompt↔ontology bridge (SPEC_UNIFIED_AUTHORING_PRODUCT §3.1.2 NET-NEW.2 /
    §12.1, OQ-1 DECIDED: ontology-as-source via ASSIGNMENT). The committed
    ``council_roles/<role>.txt`` is the SEED BASE — its safety-critical prose
    (codes-you-may-not-raise, the HL7-NKA exception, evidence requirements, the
    allergy-fabrication Tier-1 framing) is retained verbatim, NEVER silently dropped
    (S-BS-11). When the judge carries an authored assignment (an SME picked its flag
    lens via ``PUT /v1/judges/{role}``), an AUTHORED REFINEMENT section is appended,
    composed from the assigned flags' ``when_to_use`` lens (+ tier) and the role's
    ``questions_for(role)`` (ordinal-ordered). The in-process judge then re-votes
    with the authored lens — the static→live close for judges, needing no ``:8002``.

    ``assigned_flags=None`` (no authored assignment / back-compat) returns the seed
    base verbatim — the A4 parity contract: ``render_role_questions(ont, role)`` is
    byte-equal to ``load_role_prompt(role)``. Full retirement of the ``.txt``
    (rendering the entire prompt from the ontology) is DEFERRED: the ontology does
    not yet carry the full safety prose (faithfulness_judge has zero seeded
    questions; the codes-you-may-not-raise / HL7 exceptions are not in the
    ``JudgeQuestion`` model), so pushing it now would drop S-BS-11 prose. The
    ``.txt`` is the migration seed; authoring ADDS the ontology-driven refinement.

    ``ontology`` is duck-typed (``.flag(code)`` → a flag with ``.tier``/
    ``.when_to_use``; ``.questions_for(role)`` → ordinal-bearing questions) so this
    module stays decoupled from ``harness.ontology``.
    """
    base = load_role_prompt(role, prompts_dir=prompts_dir)
    if not assigned_flags:
        return base
    lens_lines: list[str] = []
    for code in assigned_flags:
        fd = ontology.flag(code)
        if fd is None:
            lens_lines.append(f"- {code}")
            continue
        tier = f" [{fd.tier}]" if fd.tier else ""
        when = (fd.when_to_use or "").strip()
        lens_lines.append(f"- {code}{tier}: {when}" if when else f"- {code}{tier}")
    refinement = [
        "",
        "=== AUTHORED REFINEMENT (ontology assignment) ===",
        "You have been assigned the following ontology flags as your lens. Raise ONLY",
        "these codes, each grounded in a specific evidence span:",
        *lens_lines,
    ]
    questions = sorted(ontology.questions_for(role), key=lambda q: q.ordinal)
    if questions:
        refinement += [
            "",
            "Refinement questions for this role:",
            *[f"{q.ordinal}. {q.text}" for q in questions],
        ]
    return base + "\n" + "\n".join(refinement)
