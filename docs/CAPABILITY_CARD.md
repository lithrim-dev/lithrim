# Lithrim Capability Card

**Status: DRAFT v1, 2026-07-04, for owner review.**
**Program: REL-OPS-1 O7 (SPEC_RELIABILITY_PROGRAM.md). This is a customer-facing
system card: what the deterministic layer verifies, what it does not, how it
abstains, and what it depends on. Uncovered failure modes are stated with the same
prominence as covered ones. No number appears here unless the mechanism that
protects it exists in the committed code cited next to it.**

Lithrim grades AI-generated artifacts (for example, clinical scribe notes) with two
layers: an LLM judge council, and a deterministic grounding layer beneath it (the
"floor") that can overrule the judges in both directions. This card is about what
each layer can honestly claim.

## 1. What the floor deterministically checks (covered failure modes)

The floor runs in two directions
(`lithrim_bench/harness/grounding.py:62-95`, `GroundedResult`):

- **Suppress:** a judge raised a confident finding; a tool-check against a pinned
  reference disproves it, and the false positive is cleared with recorded evidence.
- **Floor (inject):** the judges missed a structural violation; an artifact-level
  check fails against its pinned reference and injects a BLOCK the council did not
  produce.

Every check is declared per flag in the authored ontology and executed by a
registered contract type. The shipped contract types:

**Core, generic (`lithrim_bench/harness/grounding.py:898-917` suppress registry;
`:938-1012` floor registry):**

- `presence_check`: a "X is not in the source" finding is cleared by locating X
  verbatim in the source text.
- `source_grounding`: answer-must-be-contained-in-source faithfulness; suppresses
  only on FULL grounding, never partial.
- `evidence_presence`: evidence-integrity gate; a finding whose own quoted evidence
  spans are verbatim source text refutes itself (span-level).
- `kb_grounding`: presence check generalized to a configured knowledge base.
- `terminology_subsumption`: span-driven terminology check over a configured
  terminology tool; a term that is equal to or subsumed by (is-a) a recorded concept
  is grounded, so a judge over-flag on a valid specialization is suppressed.
- `mcp_call`: a generic authored MCP tool check (advisory, corroborating).
- `web_search`: attaches retrieved citations as evidence only. It is
  non-authoritative by construction and can never clear or raise a finding
  (`lithrim_bench/verification/tools.py:544-560`).
- `structural_jute` / `jute_gen`: structural conformance of the artifact against a
  pinned, content-hashed transform/validator (drift in the pinned template refuses,
  it does not silently pass).
- `value_presence`: a completeness floor; a pinned value pattern spoken in the source
  must appear in the artifact, else a BLOCK is injected.
- `fact_preservation` / `speaker_attribution`: bounded-extraction floors over an
  SME-pinned fact or statement, including who-said-it attribution.

**Healthcare pack (`../lithrim-pack-healthcare/healthcare/floors.py:684-698`
registries):**

- `record_presence`: a fabricated-history finding is cleared only when every
  documented past-medical-history item is grounded in the patient record
  (`floors.py:293`).
- `snomed_subsumption`: the code-based successor; each documented history item and
  each record condition resolve to SNOMED concepts, and an item is grounded only if
  its concept equals or is subsumed by a record concept (`floors.py:444`). The
  suppression is additionally span-bound: a history oracle may only clear a finding
  whose flagged span actually quotes a documented history item (SPAN-BIND-1,
  `floors.py:463-468`), so it cannot clear a finding about a fabricated exam or plan
  detail.
- `dosage_grounding`: dosage value conformance; dose tokens in the note's plan must
  match the record/reference (`floors.py:191`).
- `concept_preservation`: ingest-pinned stated/noted concept lists are grounded by
  code (equality or subsumption), so a clinically equivalent paraphrase still grounds
  and an erased or altered concept is caught (`floors.py:548`).

All suppress checks are conservative by design: they clear a finding only on
positive, recorded proof, never on silence, and a single ungrounded item leaves the
whole finding standing (see the per-executor docstrings cited above). The judge-side
withstands gate reads the same registry, never a reimplementation
(`lithrim_bench/runtime/council/signals.py:1-18`).

## 2. What the floor explicitly does NOT cover (uncovered failure modes)

This section carries the same weight as section 1. If a failure mode is listed here,
Lithrim's deterministic layer makes NO claim about it; only the (fallible) judge
layer sees it.

- **Graded completeness.** `value_presence` checks a pinned value pattern;
  `concept_preservation` checks pinned concept lists. Neither answers "is this note
  complete enough", "did it capture everything that mattered". There is no
  deterministic completeness score.
- **Clinical judgment calls.** Appropriateness of a plan, differential quality,
  escalation decisions, risk-benefit tradeoffs: not verifiable against a pinned
  reference, therefore not covered.
- **Note style and quality.** Tone, organization, readability, verbosity: not
  covered.
- **Anything requiring inference beyond the record.** The floor grounds against what
  is pinned or present (transcript, patient record, pinned references, terminology
  server). A defect visible only through outside knowledge or reasoning beyond those
  sources is not deterministically checkable.
- **Defects with no declared contract.** The floor runs only where a flag has an
  authored verification contract. A flag without a contract, or a contract whose
  declared type has no registered executor, is surfaced by the readiness preflight
  (`lithrim_bench/harness/readiness.py:1-46`) but is not silently graded. At the
  verdict layer this is made explicit per grade: `ground()` labels every surviving
  finding with a coverage tag (`grounded` / `cleared` / `declined` / `unrefuted` /
  `judge_only` / `reference` / `null`) and stamps `floor_backstopped` — **False when a
  BLOCK rests solely on judge-only findings the deterministic floor never grounded**, so
  a judge-only reject is never presented as if the floor grounded it. The annotation is
  purely derived and does not change the grade (`ground()` in
  `lithrim_bench/harness/grounding.py`; surfaced by `composite()` in `report.py`).
- **Content leakage between corpora and similar-but-not-identical duplication** in
  evaluation data (see `docs/POLICY_HOLDOUT_HYGIENE.md`, Enforcement status).

## 3. Abstention semantics (CANNOT-GROUND)

The floor is a selective predictor: it answers only where it can verify, and
declines everywhere else. The tri-state rule is uniform
(`lithrim_bench/verification/spec.py:6-15`):

- conforms is True: violation disproven, the flag MAY be cleared.
- conforms is False: violation confirmed, the flag is kept or raised.
- conforms is None: inconclusive, the flag STAYS OPEN. A tool never clears a flag by
  silence.

Concretely:

- A flag with no route, an inconclusive tool, or a tool error resolves UNRESOLVED and
  stays open (`lithrim_bench/verification/router.py:28`).
- An inconclusive floor contract (service drift, no-compile, not configured) is
  recorded but NEVER flips the verdict (`lithrim_bench/harness/grounding.py:78-84`).
- Network or transport failures are inconclusive, never a silent clear
  (`lithrim_bench/verification/tools.py:429`).
- Non-decodable artifacts, empty extractions, and unresolved terms all leave the
  finding standing (pack executor docstrings,
  `../lithrim-pack-healthcare/healthcare/floors.py:307-316`, `:459-461`).

The practical meaning for a customer: a deterministic clear or block always carries
recorded evidence; where the floor cannot ground, it says so and defers, it does not
guess.

## 4. Version dependencies

Deterministic verdicts depend on versioned inputs. Each dependency below is stamped
or guarded by shipped code, except the one marked in flight.

- **Terminology edition, stamped per verdict.** Every terminology-subsumption
  execution records the terminology release that decided it, or the honest
  `"unrecorded"` when the edition lookup is unavailable; the lookup can never change
  a verdict (`lithrim_bench/harness/grounding.py:48-57`, `:695-716`; commits
  `358abb4`, `1dbb61f`; the edition is rendered on the suppression evidence in the
  UI).
- **Provider-drift canary.** A scheduled re-grade of a small frozen golden set diffs
  verdict-by-verdict against a pinned baseline and exits non-zero on any flip
  (`scripts/canary_judges.py`, `lithrim_bench/canary.py:13-15`, `:98`). Known
  limitation, stated in the tool itself: it pins configured model identifiers, not
  per-response provider fingerprints.
- **Config-drift refusal on replays.** Every grade is stamped with a signature over
  the grade-determining config, including per-judge criterion, sampling count,
  temperature, and the digests of any pinned optimization demos
  (`lithrim_bench/harness/replay.py:62`, `:117-155`; `scripts/run_eval.py:382`). A
  replay whose config drifted is refused as stale rather than served as fresh
  (`replay.py:157`, `is_fresh`).
- **Dated-alias policy (O4): IN FLIGHT.** Policy for date-stamped model aliases is
  being built in the current wave and is NOT yet a shipped guarantee. It is listed
  here so its absence is visible, not implied.

## 5. The judge layer's honest status

- **LLM judges are a pluggable commodity slot.** The judge model binding rides a
  provider seam declared in the plugin registry
  (`lithrim_bench/harness/plugins.py`; the `build_judge_lm` provider resolution).
  Any capable model can sit in a seat. Lithrim's differentiated claim is the
  deterministic layer around the judges, not the judges themselves.
- **Judge variance and miss modes are measured, not denied.** Per-judge sampling
  count and temperature are explicit, signature-visible configuration
  (`lithrim_bench/runtime/council/sampling.py`; `lithrim_bench/harness/replay.py:117`),
  the canary measures behavioral drift over time (section 4), and judge optimization
  reports its held-out delta win-or-loss with the accept gate never loosened
  (`lithrim_bench/runtime/council/judge_optimize.py:378-380`;
  `docs/POLICY_HOLDOUT_HYGIENE.md`).
- **Measured findings** (internal validation, 2026-07, publication in preparation):
  - The deterministic layer suppressed judge over-flags on clean
    terminology-subsumption cases while leaving every genuine fabrication flagged.
  - A dosage value-check caught dosage errors the judge panel missed on every seeded
    case.
  - On a physician-curated external suite, the judge panel silently missed a
    substantial fraction of real defects that the deterministic checks caught.

  No further quantitative claims are made in this card. No service-level objective is
  published, because the longitudinal mechanism that would measure one is not yet
  shipped.
