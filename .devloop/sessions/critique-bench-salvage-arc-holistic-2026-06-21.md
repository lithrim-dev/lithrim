# HOLISTIC CRITIC — bench-salvage arc `645dfcd..HEAD` (FAUTH + NARR program)

> Ultracode multi-agent adversarial review (`wf_a6034bb4-c24`, 16 agents, ~1.4M tokens). 6 lenses
> authored; **5 completed** (moat / governance / floor / asafe / honesty) — the **`tests` lens
> FAILED** to return structured output (did not call StructuredOutput after 2 nudges → test-vacuity
> was only partially covered, via the floor lens). 8 raw findings → **7 survived** adversarial verify.

## VERDICT: NON-BLOCKING ISSUES
The one floor-lens BLOCKING finding (F1, unvalidated criterion code) is **downgraded to NON-BLOCKING**
on holistic evidence: it is reachable ONLY via a direct `POST /v1/criterion` call — no shipped FE
form and no agent tool wires it (ContractBuilder writes `/v1/grounding-contract`; the agent has no
criterion tool). Real latent corruption of the contract-of-record, but no shipped client path feeds
it yet. **Must be fixed before NARR-5-CRIT-b wires a tool to that endpoint.**

**Moat proven untouched by HASH (not prose):** `compliance_council.py` (`7f03a3c`), `signals.py`
(`7e9c231`), `withstands.py` (`5cc3106`), `judge_metric.py` (`84acdc8`) are byte-identical at
`645dfcd` and `HEAD`; `runtime/council/` diff-stat empty. The only engine-adjacent change
(`grounding.py`, +16/−9) is the additive optional `pack=` param (`_pack_registries(pack or
_active_pack())`) — the no-arg withstands/grade path is byte-behaviour-identical.

## SURVIVING FINDINGS (ranked)

**F1 — [HIGH, downgraded BLOCKING→NON-BLOCKING] the snapshot writer accepts an unvalidated/empty/
malformed code into the contract-of-record.** `criterion.py:103-113` · `app.py:1813-1814`.
`CriterionRequest.code` is a bare `str` (no pattern); `splice_gradeable_criterion` does tier/owner/dup
checks but NO code-shape check. **Reproduced live:** `splice('_core','','TIER_2','risk_judge')` landed
`''` into `tiers["TIER_2_HIGH_RISK"]` AND `lenses["risk_judge"]` (the withstands scope authority).
No test pins code-shape rejection. **Fix:** pydantic `Field(pattern=r"^[A-Z][A-Z0-9_]*$")` + a guard in
`splice_gradeable_criterion` + a RED test feeding `""`/`"  "`/`"a;DROP"`.

**F2 — [NON-BLOCKING] audit write sits OUTSIDE the criterion endpoint's atomic-rollback block.**
`app.py:1882-1901`. The rollback `try/except` ends before `AuditLog.record`; an audit-DB fault leaves a
snapshot mutation with NO AuditRecord (§2B violation on the one snapshot writer). **Caveat:** inherited
house style (`put_ontology_endpoint`, delete-flag do the same), present at parent — not an arc
regression, but it lands on the most-consequential writer. The cited `record(rec, conn=)` remediation
is mis-attributed (that's a SQLite-txn primitive; the two writes are filesystem). **Fix:** extend the
try/except over the audit; on audit failure restore BOTH the snapshot AND the ontology overlay.

**F3 — [NON-BLOCKING] the audit record under-captures the snapshot delta.** `app.py:1898-1899`. The
splice mutates 3 keys (`tiers` + `lenses` + `tier1_owners`-for-T1) but the AuditRecord `before`/`after`
records only `tiers`. The `lenses` raise-authority grant + the T1 one-strike wiring are omitted from the
canonical diff. **Fix:** record the full `lenses`/`tier1_owners` slices; assert audit content in a test.

**F4 — [NON-BLOCKING] `value_presence match='all'` uses substring containment.** `floors.py:312-313`.
`_norm(t) in hay` (lowercase+whitespace, no tokenization) → a dropped `5 mg` passes because `"5 mg" ⊂
"metoprolol 25 mg"`. Weaker than the `dosage_grounding` twin it claims to invert (which uses dose-token
SET membership). Under-fires (false-negative), never false-blocks → determinism intact. The floor test
dodges this with non-colliding 25/40mg. **Fix:** word-boundary/token match (or reuse the dose-token set).

**F5 — [NON-BLOCKING] `value_presence match='any'` false-negative on an unrelated same-token mention.**
`floors.py:300`. `re.search(value_regex, artifact)` hits a bare token ANYWHERE, unlinked to the concept.
Repro: source erases the vaccine refusal but the note says "declined to provide their SSN" → `re.search`
hits "declined" → `conforms=True`, the BLOCK silently suppressed. The docstring's "honest limit"
documents only the false-POSITIVE direction; this false-negative is named nowhere. **Fix:** document the
direction now; properly, locus-scope the search or use the SNOMED-coded oracle (FAUTH-3b, already named).

**F6 — [NIT] the writer mutates the TRACKED in-repo pack snapshot in place.** `criterion.py:113,123`.
The ontology flag goes to an isolated workspace working-copy, but the snapshot splices at the tracked
pack root — so `POST /v1/criterion` dirties the working tree for an in-repo `tier:core` pack (asymmetric
with the ontology overlay). Bare `write_text` (no temp+`os.replace`) is also non-atomic vs a concurrent
reader. **Fix:** workspace-scoped snapshot overlay + atomic temp-write-then-replace.

## COMPLETENESS CRITIC — what this review did NOT cover
1. **The FE tree (517 lines / 13 shell files) had NO dedicated lens** — `ContractBuilder.jsx`,
   `ClinicianVerdict.jsx` (new +106), `VerdictCard.jsx`, the `artifact.jsx` net-rewrite. The locked
   conversational-first PRODUCT INVARIANT (`SPEC_CONVERSATIONAL_FIRST.md`) was NOT audited, and
   `npx vitest run` was not run. (Spot-check only: ContractBuilder writes `/v1/grounding-contract`,
   Save gated on `paramsValid && flag_code && question`.)
2. **The `tests` lens crashed** → test-vacuity was only partially covered (F1's "no code-shape test" +
   F4's "test dodges with non-colliding doses" surfaced via the floor lens). A re-run of the tests lens
   is owed.
3. **Audit replayability unverified** — F2/F3 are about write-completeness; nobody checked a downstream
   reader can reconstruct a criterion-creation, or that `target.type="criterion"` is recognized elsewhere.
4. **`category="completeness"` grade-time semantics untested** — the default flows into the overlay flag;
   nobody verified the council treats a self-authored `completeness` flag identically to a seeded one.
5. **The author-time vs grade-time pack-agreement seam** (the `pack=` arg's BFF caller) is byte-safe at
   the moat read but untested for author-gate ⇄ grade-time agreement.

## WHAT'S GENUINELY SOLID (per-cycle critics + this pass agree)
- The moat is untouched, proven by hash. The grounding change is the textbook additive-optional-param.
- The criterion writer's gate ordering is fail-closed: tier-gate first, pack resolved server-side
  (not request-spoofable), STRICTER than the license gate, all validation precedes any write, the minted
  code becomes admissible by construction via the unchanged `gradeable_flags_outside_snapshot` gate.
- A-SAFE clean across the whole arc: 20 agent tools (the arc added none), no reachable paid path, the
  snapshot writer is human-endpoint-only (the agent has no path to mint a code).
- The case-10 APPROVE→BLOCK flip is honest — floor-driven, real fixture, tri-stated to never flip by
  silence; the honesty lens found the arc honest overall (the Gate-0 "swap" nit was refuted — genuine
  0 net-new from the same physical root).
