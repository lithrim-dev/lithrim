"""REL-3 setup-correctness — the documented setup path IS the working path.

Pins the community-release phase-3 fixes (seams S-REL-4/7/9/12): the compose file
passes the chat env vars it documents, the extras strings agree across README /
CONTRIBUTING (and the devstack under-install hint names a bootable set), the two
vote tests guard their `openai`-transitive import so a bare clone collects clean,
the bundled JUTE mapper image is digest-pinned (immutable), and `make demo` invokes
`python3` (the binary a stock macOS/Linux box actually has). Stdlib-only text
parses — $0, offline, no extras required to run this file.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_EXTRAS_RE = re.compile(r'pip install -e ["\']\.\[([^\]]+)\]["\']')


def _extras(text: str) -> list[set[str]]:
    return [set(m.split(",")) for m in _EXTRAS_RE.findall(text)]


def _compose() -> str:
    return (REPO / "docker-compose.yml").read_text(encoding="utf-8")


def _bff_block() -> str:
    text = _compose()
    assert "\n  bff:" in text and "\n  ui:" in text, "compose services moved"
    return text.split("\n  bff:")[1].split("\n  ui:")[0]


def test_compose_passes_chat_env_to_bff():
    """(a) README documents LITHRIM_CHAT_API_KEY/LITHRIM_CHAT_MODEL as the env chat
    path; the bff service must actually pass both through."""
    bff = _bff_block()
    for var in ("LITHRIM_CHAT_API_KEY", "LITHRIM_CHAT_MODEL"):
        assert re.search(rf"^\s+{var}: \$\{{{var}:-\}}\s*$", bff, re.M), (
            f"docker-compose.yml bff environment must pass through {var}"
        )


def test_extras_strings_consistent():
    """(b) The README full-suite line and CONTRIBUTING agree on the extras set
    (incl. [agent], what CI installs); the BYOK/devstack under-install hint names
    the same bootable [bff,council,verification] set in both surfaces."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    contributing = (REPO / "CONTRIBUTING.md").read_text(encoding="utf-8")
    devstack = (REPO / "scripts/dev/devstack.sh").read_text(encoding="utf-8")

    full_suite_lines = [ln for ln in readme.splitlines() if "full suite" in ln]
    readme_full = [s for ln in full_suite_lines for s in _extras(ln)]
    assert readme_full, "README full-suite line lost its pip install extras string"
    contrib_sets = _extras(contributing)
    assert contrib_sets, "CONTRIBUTING lost its pip install extras string"
    # CONTRIBUTING also documents a minimal .[dev] install; the FULL-suite set is its
    # maximal extras string — that is the one the README full-suite line must match.
    contrib_full = max(contrib_sets, key=len)
    assert readme_full[0] == contrib_full, (
        f"README full-suite extras {sorted(readme_full[0])} != "
        f"CONTRIBUTING full-suite extras {sorted(contrib_full)}"
    )
    assert "agent" in readme_full[0], "full-suite extras must include [agent] (CI parity)"

    boot_set = {"bff", "council", "verification"}
    assert boot_set in _extras(devstack), (
        "devstack.sh under-install hint must name .[bff,council,verification]"
    )
    assert boot_set in _extras(readme), (
        "README BYOK path must document the working .[bff,council,verification] extras"
    )


def test_vote_tests_guard_the_openai_transitive_import():
    """(c) The two vote tests import `stages` (→ compliance_council → openai at module
    load); a bare install must SKIP them, not error at collection."""
    for name in ("test_repro_r2_votes.py", "test_vote_rationale.py"):
        src = (REPO / "tests" / name).read_text(encoding="utf-8")
        guard = src.find('pytest.importorskip("openai")')
        runtime_import = src.find("from lithrim_bench")
        assert runtime_import != -1, f"{name}: runtime import moved"
        assert guard != -1, f"{name}: missing pytest.importorskip('openai') guard"
        assert guard < runtime_import, f"{name}: guard must precede the runtime import"


def test_compose_jute_default_image_is_digest_pinned():
    """(d) The bundled mapper default must be an immutable digest pin, not the mutable
    feat-sqlite-backend branch tag."""
    m = re.search(r"image: \$\{JUTE_IMAGE:-([^}]+)\}", _compose())
    assert m, "jute service image default not found in docker-compose.yml"
    assert "@sha256:" in m.group(1), (
        f"jute default image {m.group(1)!r} must be digest-pinned (@sha256:…)"
    )


def test_makefile_demo_uses_python3():
    """(e) `make demo` is the zero-config front door; `python` is not guaranteed on
    PATH (stock macOS/Debian), `python3` is."""
    mk = (REPO / "Makefile").read_text(encoding="utf-8")
    demo_lines = [ln for ln in mk.splitlines() if ln.startswith("demo:")]
    assert demo_lines, "Makefile demo target not found"
    assert "python3 scripts/demo.py" in demo_lines[0], (
        "make demo must invoke python3, not bare python"
    )
