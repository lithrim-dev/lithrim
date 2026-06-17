"""NARR-7 (P-GEN) — JUTE-generated ingest for an ARBITRARY NEW source (GitHub issues⋈comments).

The "eval anything" generality: the same generate -> live-gate -> refine extractor loop, but on
a genuinely NEW shape (GitHub issues + comments, join-by-key) instead of a StoryWorld re-proof.
Two things this asserts, both $0/offline (mock :3031 + the LM):

  * G1 — the EXTRACTOR's generation grounding teaches the JOIN idiom + the deployed-runtime
    quirks (the empirically-derived set that took the GitHub first-shot 0/3 → a refine 3/3),
    via an EXTRACTOR-ONLY addendum — the VALIDATOR's excerpt (render_dsl_excerpt as jute_dspy
    uses it) stays BYTE-IDENTICAL (R1, the #1 correctness risk).
  * G3 (offline slice) — score_extraction over the committed GitHub fixture with the known-good
    pinned template yields 6 cases, zero-null, the issue_title correctly joined; a TRAP template
    (the predicate-`.0` idiom) is REJECTED (non-vacuity — the grounding+gate target a REAL
    failure, not a tautology).

No network, no LLM: :3031 is replaced by a Python oracle (FakeGithubClient) keyed off a tag in
the template string; the live convergence test is LITHRIM_NARR_LIVE-gated (a diagnostic, never a
default gate). The ingested `body` text is INERT graded DATA — never an instruction.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lithrim_bench.verification import (
    EtlpJuteClient,
    best_of_n_extractor,
    build_extractor_generator,
    score_extraction,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GH_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "narrative" / "github_newsource_sample.json"
NARRATIVE_SNAPSHOT = REPO_ROOT / "packs" / "narrative" / "taxonomy_snapshot.json"


@pytest.fixture
def github_dump() -> dict:
    return json.loads(GH_FIXTURE.read_text())


# the known-good per-comment normalizer for the GitHub shape — emit ONE record per comment,
# join the issue title by issue_number. Carried verbatim so the offline oracle can recognize
# "the golden GitHub template" (mirrors PROVEN_TEMPLATE in test_jute_extractor.py). Uses the
# DOUBLE-quoted literal + `+` concat + structured `$if`/`$reduce` idioms G1 grounds.
GH_GOLDEN_TEMPLATE = """$map: $ resource.comments
$as: cm
$body:
  $let:
    issue:
      $reduce: $ resource.issues
      $as: [acc, i]
      $start: null
      $body: { $if: $ i.number = cm.issue_number, $then: $ i, $else: $ acc }
  $body:
    case_id: $ "gh-" + toString(cm.id)
    issue_number: $ cm.issue_number
    issue_title: $ issue.title
    author: $ cm.author
    source: github
    response: $ cm.body
"""


# --------------------------------------------------------------------------- #
# FakeGithubClient — a Python oracle standing in for the live :3031 engine on the GitHub shape.
# "golden" = the per-comment join; "trap" = the predicate-`.0` idiom that maps INTO each match
# → the join collapses to [] so issue_title comes back null (A3-A6 §4.2 boundary). The bench is
# the oracle, not JUTE.
# --------------------------------------------------------------------------- #
def _apply_github_golden(dump: dict) -> list[dict]:
    issues = {i["number"]: i for i in dump["comments"] and dump["issues"]}
    out: list[dict] = []
    for cm in dump["comments"]:
        issue = issues.get(cm["issue_number"]) or {}
        out.append(
            {
                "case_id": f"gh-{cm['id']}",
                "issue_number": cm["issue_number"],
                "issue_title": issue.get("title"),
                "author": cm["author"],
                "source": "github",
                "response": cm["body"],
            }
        )
    return out


def _apply_github_trap(dump: dict) -> list[dict]:
    """The predicate-`.0` join TRAP: `issues.*(this.number=key).0.title` maps `.0` INTO each
    match → [] → the issue lift is null. Required keys (issue_title is NOT required, but a
    mis-join also strands case_id/response when the iterate-target is wrong) come back null."""
    rows = _apply_github_golden(dump)
    for r in rows:
        r["issue_title"] = None
        r["response"] = None  # the join collapsed → required `response` stranded
    return rows


class FakeGithubClient:
    _TAGS = ("noncompile", "trap", "short", "golden")

    def __init__(self, dump: dict, default: str = "golden") -> None:
        self.dump = dump
        self.default = default
        self.persisted: list[tuple[str, str]] = []

    def _kind(self, template: str) -> str:
        for tag in self._TAGS:
            if tag in (template or ""):
                return tag
        # the golden template is recognized by its join idiom (no tag needed)
        if "i.number = cm.issue_number" in (template or ""):
            return "golden"
        return self.default

    def test_template(self, template: str, sample_input):
        kind = self._kind(template)
        if kind == "noncompile":
            return {"compiled": False, "output": None, "error": "Jute compile: boom"}
        if kind == "trap":
            return {"compiled": True, "output": _apply_github_trap(self.dump), "error": None}
        if kind == "short":
            return {"compiled": True, "output": _apply_github_golden(self.dump)[:3], "error": None}
        return {"compiled": True, "output": _apply_github_golden(self.dump), "error": None}

    def persist_or_update(self, title: str, yaml_template: str) -> dict:
        self.persisted.append((title, yaml_template))
        return {"id": 606, "title": title, "action": "created"}


# --------------------------------------------------------------------------- #
# A1 (G1) — the EXTRACTOR excerpt carries the join idiom + trap warnings; the VALIDATOR
# excerpt is BYTE-UNCHANGED (non-regression, R1).
# --------------------------------------------------------------------------- #
# the parent (d0beed8) validator excerpt SHA256 over a fixed spec — frozen so a future edit to
# the SHARED _RUNTIME_NOTES that regresses the VALIDATOR path is caught byte-for-byte (R1).
_PARENT_VALIDATOR_EXCERPT_SHA = (
    "c4df61e85d08a943aea27f4fed11afade39dddd57a4560240d60205847b2fd2e"
)


def test_extractor_excerpt_grounds_join_and_traps_validator_unchanged():
    import hashlib

    from lithrim_bench.verification import render_dsl_excerpt
    from lithrim_bench.verification.jute_dspy import _RUNTIME_NOTES

    spec = {"directives": {}, "operators": {"precedence_order": []}}

    # the VALIDATOR excerpt (jute_dspy's call shape) — must be byte-identical to the parent.
    validator_excerpt = render_dsl_excerpt(spec, include_envelope_example=False)
    assert (
        hashlib.sha256(validator_excerpt.encode()).hexdigest()
        == _PARENT_VALIDATOR_EXCERPT_SHA
    ), "the VALIDATOR excerpt changed — the extractor addendum leaked into the shared path (R1)"
    assert _RUNTIME_NOTES in validator_excerpt
    # the extractor-only grounding facts MUST NOT have leaked into the validator path. (NOTE:
    # `$reduce` is legitimately already in _RUNTIME_NOTES — these are addendum-ONLY markers.)
    assert "DOUBLE QUOTES" not in validator_excerpt
    assert "find-by-key" not in validator_excerpt
    assert "TRAP" not in validator_excerpt
    assert "assoc" not in validator_excerpt

    # the EXTRACTOR excerpt — the additive grounding (a for_extractor=True flag or a dedicated
    # render_extractor_excerpt). The validator excerpt is a strict PREFIX-or-subset; the
    # extractor adds the join idiom + both traps + len/groupBy.
    extractor_excerpt = render_dsl_excerpt(
        spec, include_envelope_example=False, for_extractor=True
    )
    assert validator_excerpt in extractor_excerpt  # additive, never a rewrite
    low = extractor_excerpt.lower()
    # the $reduce find-by-key JOIN idiom
    assert "$reduce" in extractor_excerpt and "find-by-key" in low
    # both join TRAP warnings
    assert "trap" in low
    assert ".0" in extractor_excerpt  # predicate-.0 trap
    assert "assoc" in low  # assoc-index keyword/string trap
    # the deployed-runtime quirks that caused the GitHub first-shot 0/3
    assert "double" in low and "quote" in low  # DOUBLE QUOTES ONLY
    assert "joinStr" in extractor_excerpt  # + concat, not variadic joinStr
    assert "len" in low and "groupby" in low  # len✓ / groupBy✓
    assert "resource" in low  # the feed-shape {resource:<input>} rule


# --------------------------------------------------------------------------- #
# A2 (G1 non-vacuity) — a TRAP template (predicate-`.0`) is REJECTED by the gate. Proves the
# grounding+gate target a REAL failure, not a tautology.
# --------------------------------------------------------------------------- #
def test_trap_template_is_rejected_by_the_gate(github_dump):
    client = FakeGithubClient(github_dump)
    s = score_extraction(client, "a trap template", github_dump, expected_count=6)
    assert s["accepted"] is False
    assert s["nulls"] > 0 and s["graded"] < 1.0


# --------------------------------------------------------------------------- #
# A3 (G3 offline) — the known-good GitHub template yields 6 cases, zero-null, join correct.
# --------------------------------------------------------------------------- #
def test_github_golden_yields_six_admissible_cases(github_dump):
    client = FakeGithubClient(github_dump)
    s = score_extraction(client, GH_GOLDEN_TEMPLATE, github_dump, expected_count=6)
    assert s["accepted"] is True
    assert s["count"] == 6 and s["nulls"] == 0
    cases = s["cases"]
    assert len(cases) == 6

    # the §4.1 eval-case envelope: each record carries the graded content (the comment body) +
    # an unlabeled, null-injection-recipe shape (ingested data is UNLABELED by construction).
    for c in cases:
        assert c["case_id"]
        assert c["artifacts"] and c["artifacts"][0]["content"]
        assert c["expected_safety_flags"] == []
        assert c["injection_recipe"] is None
        assert c["context_kind"]

    # admissibility under pack=narrative: the (empty) labels are a subset of the tier union.
    tier_union: set[str] = set()
    snap = json.loads(NARRATIVE_SNAPSHOT.read_text())
    for codes in snap["tiers"].values():
        tier_union.update(codes)
    for c in cases:
        assert set(c["expected_safety_flags"]) <= tier_union


# --------------------------------------------------------------------------- #
# A2-companion — a SHORT array (the iterated-collection mis-named) is rejected; the count
# heuristic is what catches a non-list dict ingesting as 1.
# --------------------------------------------------------------------------- #
def test_github_short_is_rejected(github_dump):
    client = FakeGithubClient(github_dump)
    short = score_extraction(client, "a short template", github_dump, expected_count=6)
    assert short["accepted"] is False
    assert short["count"] == 3


# --------------------------------------------------------------------------- #
# A6 (live, LITHRIM_NARR_LIVE=1) — the extractor GENERATES + converges against :3031 on the
# GENUINELY NEW GitHub shape (count=6, zero-null). The honest "it generalizes" evidence — NOT
# in Gate 0.
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(
    not os.getenv("LITHRIM_NARR_LIVE"),
    reason="live-service dependent; set LITHRIM_NARR_LIVE=1 with :3031 up + an LM",
)
def test_live_extractor_converges_github(github_dump):
    """G2 — the honest 'it generalizes' evidence: best_of_n_extractor GENERATES a JUTE
    transform for the GENUINELY NEW GitHub shape (join issues⋈comments by issue_number) from
    the enriched (for_extractor) grounding alone, and the live :3031 ACCEPTS it (count=6,
    zero-null). NOT in Gate 0. Default LM = BYO-Claude $0 (the trimmed ~1.6KB sample clears the
    old 120s timeout); LITHRIM_NARR_LM=azure picks the Azure DSPy adapter if the CLI misbehaves.
    """
    dspy = pytest.importorskip("dspy")
    from lithrim_bench.verification import render_dsl_excerpt

    # configure the one-time generation LM (the live gate is :3031; the LM only authors YAML).
    lm_choice = os.getenv("LITHRIM_NARR_LM", "byo-claude")
    if lm_choice in ("byo-claude", "claude", "claude-cli"):
        from lithrim_bench.runtime.council.byo_claude_lm import build_claude_cli_lm

        dspy.configure(lm=build_claude_cli_lm(claude_model=os.getenv("LITHRIM_NARR_CLAUDE_MODEL")))
    # else: rely on a pre-configured dspy.settings.lm (e.g. an Azure adapter the runner set up).

    client = EtlpJuteClient()
    excerpt = render_dsl_excerpt(
        client.get_dsl_spec(), include_envelope_example=False, for_extractor=True
    )

    def make_gen():
        return build_extractor_generator(client, excerpt, github_dump, expected_count=6)

    out = best_of_n_extractor(make_gen, _GITHUB_RULES, github_dump, n=3)
    assert out.accepted is True, f"live generation did not converge; history={getattr(out, 'history', None)}"
    s = score_extraction(client, out.jute_transform, github_dump, expected_count=6)
    assert s["count"] == 6 and s["nulls"] == 0


_GITHUB_RULES = (
    "Normalize a GitHub issues+comments dump into a per-COMMENT array of eval cases. For each "
    "entry in resource.comments, emit one record joining the matching resource.issues row by "
    "issue_number (the comment's issue_number = the issue's number), with keys: case_id "
    '("gh-" + the comment id), issue_number, issue_title (from the joined issue), author, '
    "source, response (the comment body — the graded content). Iterate over comments (6 of "
    "them), NOT the top-level dict."
)
