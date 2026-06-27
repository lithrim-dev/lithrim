"""PROMPT-EDIT-1 — an SME edits an EXISTING reviewer's prompt from the UI (no code change).

The create path (POST /v1/judges) already seeds a role prompt via write_role_prompt; the EDIT path
(PUT /v1/judges/{role}) only touched lens/model/validators, so once a reviewer existed its prompt was
code-only — defeating the SME-authorable positioning. This wires the optional ``role_prompt`` into the
PUT, reusing the existing tier:core-gated, idempotent-overwrite ``write_role_prompt`` writer.

  * core pack  → PUT with role_prompt overwrites council_roles/<role>.txt (last-write-wins) + audits it.
  * pro pack   → 422 (a licensed vertical pack's council_roles stay a backend artifact — the boundary).
  * no role_prompt key → byte-identical to before (the lens-only edit is untouched).

RED-first: put_judge_endpoint ignores role_prompt today. $0/offline; the active pack is a throwaway
copy of packs/_core (no repo-source mutation).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="needs the [bff] extra (fastapi)")

from lithrim_bench.harness.audit import Actor  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
_BFF = REPO_ROOT / "apps" / "bff"
if str(_BFF) not in sys.path:
    sys.path.insert(0, str(_BFF))

import app as bff  # noqa: E402


def _make_pack(tmp_path: Path, name: str, tier: str) -> str:
    dst = tmp_path / name
    shutil.copytree(REPO_ROOT / "packs" / "_core", dst)
    m = json.loads((dst / "pack.json").read_text())
    m["pack_id"] = name
    m["tier"] = tier
    (dst / "pack.json").write_text(json.dumps(m, indent=2))
    return name


def _pin_pack(tmp_path, monkeypatch, tier: str):
    """Active workspace pinned to a throwaway pack of the given tier; returns (pack_id, audit list)."""
    from lithrim_bench.harness import pack as pack_mod
    from lithrim_bench.harness.workspace import Workspace

    name = _make_pack(tmp_path, f"{tier}pack", tier=tier)
    existing = os.environ.get("LITHRIM_BENCH_PACKS_DIR", "")
    monkeypatch.setenv("LITHRIM_BENCH_PACKS_DIR", str(tmp_path) + (os.pathsep + existing if existing else ""))
    pack_mod._pack_root.cache_clear()
    pack_mod._council_known_codes.cache_clear()
    pack_mod.assert_pack_judges_consistent.cache_clear()
    import lithrim_bench.runtime.council.judge_assignment as _ja

    monkeypatch.setattr(_ja, "_ROLE_PROMPTS_DIR", tmp_path / name / "council_roles", raising=False)
    monkeypatch.setattr(bff.workspace, "get_active_workspace", lambda: Workspace(name="t", pack=name))
    records: list = []
    monkeypatch.setattr(bff.AuditLog, "record", lambda self, rec, **kw: records.append(rec))
    return name, records


def _put(tmp_path, role, body):
    return bff.put_judge_endpoint(
        role=role, judge=body, rationale="the SME's why", agent=None,
        db_path=tmp_path / "config.sqlite",
        default_actor=Actor(type="system", id="test"), x_actor=None,
    )


def _prompt_text(pack, role) -> str:
    from lithrim_bench.harness import pack as pack_mod

    return (pack_mod._pack_ref(pack, "council_roles") / f"{role}.txt").read_text()


def test_put_role_prompt_overwrites_the_prompt_on_a_core_pack(tmp_path, monkeypatch):
    pack, records = _pin_pack(tmp_path, monkeypatch, tier="core")
    new_prompt = "YOU ARE THE FIDELITY JUDGE — flag INTENT_ERASURE when the note drops the patient's stated intent."
    out = _put(tmp_path, "risk_judge", {"assigned_flags": [], "validator_refs": [], "model": "", "role_prompt": new_prompt})
    assert out["status"] == "ok"
    assert _prompt_text(pack, "risk_judge").rstrip("\n") == new_prompt  # last-write-wins overwrite
    # the prompt edit is audited (who/what/why) — not a silent mutation
    prompt_audits = [r for r in records if r.target.type == "judge" and "prompt" in r.action]
    assert len(prompt_audits) == 1 and prompt_audits[0].target.id == "risk_judge"


def test_put_role_prompt_on_a_pro_pack_is_locked_422(tmp_path, monkeypatch):
    from fastapi import HTTPException

    pack, _ = _pin_pack(tmp_path, monkeypatch, tier="pro")
    before = _prompt_text(pack, "risk_judge")
    with pytest.raises(HTTPException) as ei:
        _put(tmp_path, "risk_judge", {"assigned_flags": [], "validator_refs": [], "model": "", "role_prompt": "SME edit attempt"})
    assert ei.value.status_code == 422
    assert _prompt_text(pack, "risk_judge") == before  # the licensed pack's prompt is unchanged


def test_put_without_role_prompt_leaves_the_prompt_untouched(tmp_path, monkeypatch):
    pack, _ = _pin_pack(tmp_path, monkeypatch, tier="core")
    before = _prompt_text(pack, "risk_judge")
    out = _put(tmp_path, "risk_judge", {"assigned_flags": [], "validator_refs": [], "model": ""})
    assert out["status"] == "ok"
    assert _prompt_text(pack, "risk_judge") == before  # lens-only edit never touches the prompt
