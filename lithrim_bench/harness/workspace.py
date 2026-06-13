"""Workspaces — the switchable domain-setup boundary (the multitenancy primitive).

A *workspace* is a directory holding its own complete config plane. Switching the
active workspace repoints every store AND the active pack, so "all meta switches":

    out/workspaces/<name>/
        config.sqlite       agents / judges / flags / audit   (harness.config)
        collections.sqlite  run-provenance / history          (harness.collections)
        ontology/           PUT /v1/ontology working copies    (BFF draft workdir)
        out/                run-output blobs
        workspace.json      { name, pack, packs_dir, actor, owner, created_at }

The pinned ``pack`` is the workspace's DOMAIN — grades run under it (the BFF subprocesses
the grade with ``LITHRIM_BENCH_PACK=<pack>`` since the frozen council binds its pack at
import; the BFF process itself stays pack-agnostic, which is what a multi-pack / multi-
tenant host needs).

The schema carries an ``owner`` slot so a future hosted layer can gate access per
workspace without a model change — the LOCAL runtime ignores it (single-user). That is
the only seam between "local CE workspace" and "cloud tenant".
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from lithrim_bench.harness.config import init_config_db, seed_config_db

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACES_DIR = Path(
    os.environ.get("LITHRIM_BENCH_WORKSPACES_DIR", str(REPO_ROOT / "out" / "workspaces"))
)
DEFAULT_WORKSPACE = "default"
DEFAULT_PACK = "_core"


def _active_ptr() -> Path:
    return WORKSPACES_DIR / ".active"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Workspace:
    """One domain setup. Paths derive from ``name`` under WORKSPACES_DIR."""

    name: str
    pack: str = DEFAULT_PACK
    packs_dir: str | None = None  # LITHRIM_BENCH_PACKS_DIR override (None -> inherit env)
    actor: str = "you@local"  # the audit 'who' default for writes in this workspace
    owner: str | None = None  # AUTH SLOT — ignored locally; gates access in a hosted layer
    created_at: str = ""

    @property
    def dir(self) -> Path:
        return WORKSPACES_DIR / self.name

    @property
    def config_db(self) -> Path:
        return self.dir / "config.sqlite"

    @property
    def collections_db(self) -> Path:
        return self.dir / "collections.sqlite"

    @property
    def ontology_dir(self) -> Path:
        return self.dir / "ontology"

    @property
    def out_dir(self) -> Path:
        return self.dir / "out"

    @property
    def manifest_path(self) -> Path:
        return self.dir / "workspace.json"

    def to_public(self) -> dict:
        """The API view — internal absolute paths stay server-side."""
        return {
            "name": self.name,
            "pack": self.pack,
            "actor": self.actor,
            "owner": self.owner,
            "created_at": self.created_at,
        }


def _slug_ok(name: str) -> bool:
    return bool(name) and all(c.isalnum() or c in "-_" for c in name) and name[0] != "."


def list_workspaces() -> list[str]:
    if not WORKSPACES_DIR.is_dir():
        return []
    return sorted(
        p.name for p in WORKSPACES_DIR.iterdir() if p.is_dir() and (p / "workspace.json").is_file()
    )


def _read(name: str) -> Workspace:
    data = json.loads((WORKSPACES_DIR / name / "workspace.json").read_text())
    fields = {k: data.get(k) for k in ("name", "pack", "packs_dir", "actor", "owner", "created_at")}
    fields["name"] = name  # the dir name is canonical
    return Workspace(**{k: v for k, v in fields.items() if v is not None})


def _write(ws: Workspace) -> None:
    ws.dir.mkdir(parents=True, exist_ok=True)
    ws.ontology_dir.mkdir(exist_ok=True)
    ws.out_dir.mkdir(exist_ok=True)
    ws.manifest_path.write_text(json.dumps(asdict(ws), indent=2) + "\n")


def create_workspace(
    name: str,
    *,
    pack: str = DEFAULT_PACK,
    actor: str = "you@local",
    owner: str | None = None,
    packs_dir: str | None = None,
    seed: bool = True,
) -> Workspace:
    if not _slug_ok(name):
        raise ValueError(f"invalid workspace name {name!r} (use alphanumerics, '-' or '_')")
    if (WORKSPACES_DIR / name / "workspace.json").is_file():
        raise FileExistsError(f"workspace {name!r} already exists")
    ws = Workspace(
        name=name, pack=pack, actor=actor, owner=owner, packs_dir=packs_dir, created_at=_now()
    )
    _write(ws)
    if seed:  # the default workspace: build its config DB from the committed seeds (ws0_default)
        seed_config_db(db_path=ws.config_db)
    else:  # a fresh workspace starts EMPTY (own schema, no agents) — "create your first agent"
        init_config_db(db_path=ws.config_db)
    return ws


def ensure_default_workspace() -> Workspace:
    """Idempotently materialize the ``default`` workspace (the clean CE starting point —
    the ONE workspace seeded with the blank ws0_default; fresh user workspaces start empty)."""
    if (WORKSPACES_DIR / DEFAULT_WORKSPACE / "workspace.json").is_file():
        ws = _read(DEFAULT_WORKSPACE)
        if not ws.config_db.exists():  # dir exists but the config DB was wiped → re-seed
            seed_config_db(db_path=ws.config_db)
        return ws
    return create_workspace(DEFAULT_WORKSPACE, pack=DEFAULT_PACK)


def active_workspace_name() -> str:
    ptr = _active_ptr()
    if ptr.is_file():
        name = ptr.read_text().strip()
        if name and (WORKSPACES_DIR / name / "workspace.json").is_file():
            return name
    return DEFAULT_WORKSPACE


def set_active_workspace(name: str) -> Workspace:
    if not (WORKSPACES_DIR / name / "workspace.json").is_file():
        raise FileNotFoundError(f"workspace {name!r} not found")
    WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)
    _active_ptr().write_text(name + "\n")
    return _read(name)


def get_active_workspace() -> Workspace:
    """The active workspace, self-healing the ``default`` on first use."""
    ensure_default_workspace()
    return _read(active_workspace_name())


def read_workspace(name: str) -> Workspace:
    """Public read of one workspace's manifest."""
    return _read(name)


def workspaces_public() -> dict:
    """The API view: every workspace (public fields) + the active name."""
    ensure_default_workspace()
    return {
        "workspaces": [_read(n).to_public() for n in list_workspaces()],
        "active": active_workspace_name(),
    }
