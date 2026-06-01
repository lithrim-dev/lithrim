# Spec-Adherence Critique — `bench-salvage` phase `WS-6c`

> Inline-mode critique (monitor session). The bundle is flagged **HARD-GATE**
> (`index.json` + driver §Hardness:168). `/devloop-critique`'s rule is to halt
> and recommend a fresh-critic; the user elected the inline path (driver §168
> explicitly permits "User MAY elect inline"). The load-bearing independence
> property was preserved as far as inline allows: the spec was read cold, the
> port-fidelity diff (A2) and the offline oracle (A3) were **independently
> reproduced/re-run**, and the S-BS-31 finding was derived from source BEFORE
> the executor's session log was read. See the discipline self-check at the end.

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `WS-6c`
- **Driver bundle:** `bench-salvage-phaseWS-6c-council-port-driver`
- **Commits audited:** `12281e1`, `a6e5b86`, `6bae3c0` (range `fb775f4..HEAD`; `6bae3c0` = the A5-amend of the original `c25510f`)
- **Spec(s) read against:** `docs/specs/RECOMPOSITION_PLAN_ws6.md` (§5 PRESERVE-AS-IP, §6 hybrid, §Ratification); `docs/specs/SPEC_PRODUCT_SERVICE_TOPOLOGY.md` (§WS-6c, §Honest flags); driver §2/§3/§4/§5; `CLAUDE.md` core invariant #4
- **Critique mode:** `inline` (monitor self-audit; HARD-GATE — fresh-critic recommended but user-elected inline)
- **Date:** `2026-06-01`
- **Reviewer:** `monitor (inline)` (original pass written pre-amend, 2026-06-01 23:54) + reconciled at close by the closing monitor session

> **Close reconciliation (closing monitor, at `/devloop-close-phase`):** the original inline pass was written against the pre-amend tip `c25510f`; the A5 live smoke then amended that commit to `6bae3c0` (the corrected FABRICATED_HISTORY payload). Corrections applied at close, since the original predates the amend:
> 1. **Commits-audited `c25510f` → `6bae3c0`** (metadata above; appendix still lists the pre-amend hash for the record).
> 2. **The §3 NON-BLOCKING "session-log commit reference is stale" finding (below) is REVERSED in the original and is hereby corrected to a non-finding.** Post-amend reality: HEAD is `6bae3c0`, the session log correctly references `6bae3c0`, and `c25510f` is the dangling pre-amend object. No action needed.
> 3. **A5 is now PASS** (it was gated/unrun when the original was written): live v2 trio all-reject on the Azure dev resource, Mistral `confidence=None` end-to-end, verdict matches the offline oracle.
> 4. **Added NON-BLOCKING surface finding the original pass did not flag:** `__init__.py:1-54` ships documentation but **no public exports**, whereas driver §2 specified "minimal public exports (`ComplianceCouncil`, `CouncilModel`, `extract_verdict_confidence`, tier tables)." The doc/seam half landed in full; the exports half was deliberately dropped to keep `__init__` import-light so `from lithrim_bench.runtime.council import safety_flags` (the offline consumer, `scripts/seed_ontology.py:215`) stays openai-free. Consumers import from the submodule (`conftest.py:23`). Disposition: accept (sound; preserves the A1 offline core); record in the session-log `deviations[]`; optional future lazy `__getattr__` for root exports.
>
> Updated finding tally: Q1 NON-BLOCKING 2 → 3 (adds the `__init__` finding); the §3 reversed finding drops from NON-BLOCKING to non-finding. **Verdict unchanged: NON-BLOCKING FINDINGS, 0 BLOCKING.** The closing monitor independently re-verified A2 (byte-faithful at `6bae3c0`) and re-ran the oracle (16 passed / 19 with taxonomy, 1 skipped) at the post-amend tip.

---

## Verdict

**`NON-BLOCKING FINDINGS`**

The consensus IP is a **byte-faithful port of `493b533`** (independently reproduced: `compliance_council.py` = 6 import lines + 1 path; `safety_flags.py` byte-identical; `llm_provider.py`/`phi_redaction.py` = 1 import line each — zero logic change), the offline oracle is **independently green (16 passed)**, all 7 A3 behaviors trace cleanly to the real `_apply_consensus`, A1–A7 hold, and scope was held. The one substantive issue — **S-BS-31**, where v2-only leaves 3 Tier-1 flags (2 of them used in shipped `proof_case.jsonl`) without a production-resident owner, colliding with `CLAUDE.md` invariant #4 — is a **faithfully-ported backend property** (mandated verbatim by A2/decision #2) that the executor surfaced in three places, not drift. It is **not BLOCKING for this cycle** but is a high-priority **OPEN-QUESTION** that should gate WS-6c-AGENTIC (when the council scores real cases through the grade seam).

---

## 1. Surface fidelity

> Does the public API match the spec exactly?

The deliverable is a **verbatim port** (driver §2:69-74; spec §5:144-154; topology §65 "port-don't-rewrite"). I verified the ported surface against `lithrim-backend@493b533` directly (not via the zero git delta, which would hide a stale port).

| Spec definition | Implementation | Match? | Severity |
|---|---|---|---|
| spec §5:148 `_apply_consensus` (tier/owner/PHI/worst-of/artifact-override) | `compliance_council.py:1853` — diff vs `493b533` = 6 import lines + `_ROLE_PROMPTS_DIR:457` only | byte-faithful | — |
| spec §5:149 `_compose_council_verdict_v2` (llama-veto) | `compliance_council.py:1812` — unchanged | byte-faithful | — |
| spec §5:150 `_worst_of_verdicts` | `compliance_council.py:1799` — unchanged | byte-faithful | — |
| spec §5:151 tier/owner/pillar tables `TIER_1..:176`, `_TIER1_OWNERS:232`, `KNOWN_TAXONOMY_CODES:279` | `compliance_council.py:176/232/279` — unchanged | byte-faithful | — |
| spec §5:157 split-tables: `safety_flags.py` (FailureType/SAFETY_FLAG_TO_FAILURE_TYPE/get_flag_prompt_section) | `safety_flags.py` — **byte-identical** (`diff` exit 0); both files travelled | byte-faithful | — |
| spec §5:159 `extract_verdict_confidence` None-for-Mistral (never coerce) | `compliance_council.py:413` — unchanged; read at `:1979` | byte-faithful | — |
| spec §2 salvage `llm_provider` factory + 5 role prompts | `llm_provider.py` (1 import line) + `council_roles/*.txt` (all 5 **identical** to `493b533`) | byte-faithful | — |
| driver §3 dec#2 `COMPLIANCE_COUNCIL_VERSION` default | `settings.py:50` flips backend default `v1`→`v2` (flagged inline :46-50) | authorized change | — |

**Findings:**

- No surface drift detected. Every ported public symbol matches `493b533` exactly, modulo the mechanical adaptation the commit claims (`app.*` → package-relative imports + `_ROLE_PROMPTS_DIR`). The single intentional surface change — `settings.py:50` default `v2` — is authorized by driver decision #2 (§3:83) and the §Ratification Q1 v2-only lock (spec:260).
- `[NON-BLOCKING]` Driver §2 deliverable #3 (driver:71) names "the **5** `AZURE_OPENAI_DEPLOYMENT_*`", but `493b533/app/config.py` has **4** (`:85,86,216,217`) and the council read-set references exactly those 4 (`llm_provider.py:41/46/57/64`); `settings.py:39-43` correctly subsets 4. **The impl is right; the driver miscounts.** Already surfaced by the executor at plan-review (session log `deviations[1]`). Disposition: correct driver text to "4".
- `[NON-BLOCKING]` Driver §1:57 / §2:69 cite `JUDGES_V2` as a module-level port symbol; at `493b533` there is no such constant — the v2 trio is built inline in `ComplianceCouncil.__init__` (`compliance_council.py:463-497`); only a comment at `:381` names it. The inline tuple was ported. Citation drift in the driver, surfaced at plan-review (`deviations[5]`). Disposition: correct driver text.

---

## 2. Behavioral fidelity

> spec assertion → test that exercises it → implementation site.

Fixtures drive the **real** `ComplianceCouncil._apply_consensus` (`conftest.py:21-25`) with the **real** per-judge dict shape (`conftest.py:38-49`); I verified key-by-key that the impl reads exactly those keys (`decision`/`findings`/`confidence`/`errors`/`model` at `:1986/:1899/:1979/:1578/:1985`; `taxonomy_code`/`evidence_spans` at `:1911/:1914`). No vacuous-pass risk from key-name drift. I also **re-ran the oracle independently: 16 passed in 0.31s** (offline, `debuglithrim` 3.10.15).

### Behavior 1: Tier-1 owner one-strike

- **Spec assertion:** §5:148 — "Tier-1 one-strike (owner OR ≥2 evidence-judges)".
- **Test:** `test_consensus.py:31` `test_tier1_owner_one_strike_rejects` — `risk_judge` (owner of FABRICATED_ALLERGY) solo + grounded span → asserts `decision==reject`, `tier1_triggered==[FABRICATED_ALLERGY]`, `artifact_verdict==BLOCK`. Complemented by `:47` (non-owner solo → downgrade to `tier2_flagged`/`needs_review`) and `:66` (2-judge corroboration → reject regardless of ownership).
- **Implementation:** `compliance_council.py:2047-2092` (owner-gated one-strike; off-domain downgrade reads `judges[0]["model"]` at `:2047`, other-decisions at `:2033`).
- **Chain closes?** YES — all three sub-rules of the spec clause are exercised against the real code path.

### Behavior 2: None-confidence (Mistral) tolerance

- **Spec assertion:** §5:159 — `extract_verdict_confidence` "returns None for Mistral by design and must NEVER be coerced to 1.0"; §5:153 BRS-3 None-tolerance.
- **Test:** `test_consensus.py:186` `test_none_confidence_skipped_in_average` (`[0.92, None, None]`→0.92) + `:197` `test_all_none_confidence_falls_back_to_zero` (all-None→0.0 + `uncertainty=True`).
- **Implementation:** `compliance_council.py:1979` reads `result.get("confidence")`; averaging filters None (`:1620` `if m.get("confidence")` pattern) rather than coercing.
- **Chain closes?** YES — both the skip-None and the degenerate-all-None floor are asserted; the "never coerce to 1.0/0.0" invariant is the exact behavior tested.

### Behavior 3: v2 llama-veto-approve (and its safety-floor gate)

- **Spec assertion:** §5:149 — "if `faithfulness_judge`(Llama)==approve AND no other rejects → approve, else worst-of; gated OFF when `tier1_triggered` non-empty (safety floor)".
- **Test:** `test_consensus.py:127` veto-on (over-strict gpt-4.1 restored to approve), `:141` veto-off-by-reject (worst-of → reject), `:151` veto-off-under-Tier-1 (grounded never-event pulls reject despite Llama approve).
- **Implementation:** `_compose_council_verdict_v2` `compliance_council.py:1812`; judge-decision map `:1844`; Tier-1 floor gate `:2349-2350`.
- **Chain closes?** YES — all three branches (restore / disable-by-reject / disable-by-Tier-1-floor) are independently exercised.

**Findings:**

- No behavioral drift. A3's full required set (Tier-1 one-strike, Tier-2 2+, PHI-FP suppression, NKA, llama-veto, artifact-BLOCK, None-confidence) is covered by 16 tests, plus a v1/v2 differential (`:248`) proving both ported branches are live (driver dec #2). NKA is correctly modeled as a **prompt-resident** assertion (`test_consensus.py:233`), matching spec §5:152 (NKA lives in role prompts + `build_prompt`, not consensus math) — a judgment call surfaced at plan-review and confirmed accurate.

---

## 3. Out-of-scope intrusion

> Anything not in the driver's deliverables list is intrusion.

Driver §2 deliverables (verbatim): (1) `compliance_council.py` refresh; (2) `safety_flags.py` refresh; (3) `llm_provider.py` + `council_roles/` + `settings.py`; (4) `scripts/snapshot_taxonomy.py` S-BS-30; (5) `runtime/council/tests/`; (6) session log.

`git diff --stat fb775f4..HEAD` (council-only; the interleaved shell commit `fb775f4` is the base, correctly excluded):

```
lithrim_bench/runtime/council/__init__.py          |  54 ++   (pkg docs — deliv #3 framing)
lithrim_bench/runtime/council/settings.py          | 347 +-   (16-field subset — deliv #3)
lithrim_bench/runtime/council/tests/{conftest,test_consensus,test_live_smoke}.py | new (deliv #5)
scripts/snapshot_taxonomy.py                       |  29 +-   (S-BS-30 — deliv #4)
taxonomy/taxonomy_snapshot.json                    |   5 +-   (re-snapshot — deliv #4/A4)
tests/test_taxonomy.py                             |  11 +-   (APPROVED-MID-CYCLE)
pyproject.toml                                     |  12 +-   ([council] extra + testpaths — APPROVED-AT-PLAN)
```

The headline IP files (`compliance_council.py`, `safety_flags.py`, `llm_provider.py`, `phi_redaction.py`, `council_roles/`) carry **zero git delta** — they trace to the M1 parking commit `8f9beae` (2026-05-29). The executor's disposition (verify the parked mirror is byte-faithful to `493b533` rather than blindly re-overwrite) is defensible and the end state is verified-correct; see §4 Ambiguity 3.

**Findings:**

- All diffed files map to a deliverable or an explicitly-approved deviation. No drive-by refactors, no formatting passes, no LangGraph/agents/persistence/KB/DSPy work (A7 verified: backend clean `@493b533`, no `etlp-mapper` edits, no `grade.py`/`run_eval.py`/`report.py` change — A6). **No intrusion detected.**
  - `phi_redaction.py` (a 4th ported code file beyond the driver's 3-file list) — **authorized** APPROVED-AT-PLAN (`deviations[0]`): `compliance_council.py:29` hard-imports `sanitize_prompt`; load-bearing, Mongo-free.
  - `tests/test_taxonomy.py:` (`{behavior_judge,risk_judge}<=owners` → `risk_judge in owners` + `behavior_judge not in owners`) — **authorized** APPROVED-MID-CYCLE (`deviations[3]`); a necessary consequence of the S-BS-30 production_judges flip, with rationale comment + S-BS-31 link. The guarded invariant (WRONG_DOSAGE retains a production-resident path via `risk_judge`) is preserved.
  - `pyproject.toml` `[council]` extra + `testpaths` — **authorized** APPROVED-AT-PLAN (`deviations[2]`); keeps openai/tenacity out of the offline core (A1).
- `[NON-BLOCKING]` **Session-log commit reference is stale.** The log (`commits[2]`) names the test commit `6bae3c0` titled "…live Azure smoke (A5 PASS)"; HEAD is `c25510f` "…gated live Azure smoke" (amended after the log was written — `6bae3c0` survives only as a dangling object). The committed code is the corrected FABRICATED_HISTORY smoke. Disposition: refresh the hash at close (cosmetic).
- `[NON-BLOCKING]` **Commit `c25510f` body misnames the smoke case.** Its body says "by-construction FABRICATED_ALLERGY case → expected reject", but the committed `test_live_smoke.py:44-77` and the session log use **FABRICATED_HISTORY** (the case was switched precisely to avoid the S-BS-31 orphan minefield, `test_live_smoke.py:49-51`). Leftover wording from the pre-switch case. Given this repo's diagnose-before-edit discipline on accurate records, worth a one-line amend if the commit is ever reworded; otherwise log it.

---

## 4. Spec ambiguity surfaced

### Ambiguity 1: invariant-#4 collision under v2-only (S-BS-31) — PRIMARY

- **Spec text:** `CLAUDE.md` core invariant #4 — "Every flag has a `production_judges`-resident owner per `tier1_owners`. Flags whose only owner is `source_message_judge` (declared but not running) must be excluded or reassigned; **never silently scored**." Spec §Ratification:267 mandates S-BS-30 (derive `production_judges` from the v2 config). Spec §5:160 flagged `source_message_judge` as declared-but-not-running yet present in `_TIER1_OWNERS`. Driver §2:69 + A2 mandate porting `_TIER1_OWNERS` **verbatim**.
- **Implementation decided:** the S-BS-30 derivation (`snapshot_taxonomy.py`) sets `production_judges = [risk_judge, policy_judge, faithfulness_judge]` (`taxonomy_snapshot.json`). The ported `_TIER1_OWNERS` (`compliance_council.py:234/241/249`) gives `MISSING_ALLERGY`={behavior,source_message}, `FABRICATED_CONSENT`={behavior,source_message}, `VALUE_MISMATCH`={behavior} — **none in the v2 trio**. So these 3 Tier-1 never-events lose the single-judge one-strike path under v2-only (corroboration-only escalation remains). **2 of the 3 (`MISSING_ALLERGY`, `VALUE_MISMATCH`) appear in shipped `examples/proof_case.jsonl`** (`expected_safety_flags`, ×3 each). **WS-6c's S-BS-30 fix is the proximate cause** — pre-cycle, the hardcoded `production_judges` included `behavior_judge`, so these flags *had* a production owner.
- **Alternatives that would also be spec-compliant:** (a) reassign these 3 codes to a v2-trio owner in `_TIER1_OWNERS` (a backend IP change — would *violate* this cycle's verbatim-port mandate, hence correctly out of scope); (b) accept corroboration-only escalation under v2 and document it; (c) re-activate `behavior_judge`.
- **Question for spec author:** Under v2-only, should `MISSING_ALLERGY` / `FABRICATED_CONSENT` / `VALUE_MISMATCH` retain a single-judge one-strike path (→ reassign owner to risk/policy/faithfulness), or is corroboration-only escalation the accepted v2 safety posture? This is a safety-policy decision above the executor's remit.
- **Recommended resolution:** **OPEN-QUESTION, not BLOCKING for WS-6c.** The driver mandated a verbatim port (A2) and explicitly scoped owner-reassignment *out* (§4:97); the executor honored that, the end state matches the backend's real v2 property, and the collision is **not silent** — it is surfaced in `seams_opened[S-BS-31]`, the commit body (`a6e5b86`), and `__init__.py:34-36`. All A1–A7 pass. **Recommend S-BS-31 be made a gate on WS-6c-AGENTIC** (the cycle that wires this council into the live grade seam, where these flags would score real cases) and resolved there or at WS-6c-DSPy.

### Ambiguity 2: "lint green" (A4) does not prove invariant #4

- **Spec text:** A4 (driver:111) accepts on "lint green". `CLAUDE.md` invariant #4 reads as an *admissibility* criterion ("a case is admissible only if … every flag has a `production_judges`-resident owner").
- **Implementation decided:** `lint_golden_against_taxonomy.py` enforces only **D1** (every `expected_safety_flags` code ∈ `KNOWN_TAXONOMY_CODES`, `:6-7`) and **D8** (Tier-1 ⇒ verdict reject + set-valued rationale, `:66-74`). It does **not** check owner-residency. `seed_ontology.py:34` documents this as deliberate: "the invariant-#4 exclusion is a **WS-4 scoring-time rule, not a seed-time edit**."
- **Alternatives:** add an owner-residency check to the lint (would have flagged S-BS-31's `proof_case.jsonl` rows on re-snapshot), or keep #4 a scoring-time rule and document that "lint green" ≠ "#4 holds".
- **Question for spec author:** Should the admissibility lint gain an owner-residency check so a `production_judges` change can never silently strand a shipped case's flag (closing the gap that let S-BS-31 ride a green lint)?
- **Recommended resolution:** OPEN-QUESTION. Pre-existing design (not WS-6c drift); the executor's "lint gates D1/D8 only" claim (commit `a6e5b86`) is **accurate**. Worth locking as a separate lint-hardening cycle, paired with the S-BS-31 decision.

### Ambiguity 3: "refresh from 493b533" satisfied by verification, not re-commit

- **Spec text:** driver §2:69 "refresh from `493b533`"; §4:97-98 + spec §5:158 "Do NOT port from the stale parked mirror … the mirror **DIFFERS** (exit=1) … Port from `493b533`."
- **Implementation decided:** the executor re-derived from `493b533`, found the result **byte-identical to the already-parked mirror** (modulo the mechanical transform), and therefore committed **zero delta** on the IP files; the A2 evidence lives in the session log + my independent reproduction.
- **Alternatives:** blindly overwrite the files (same bytes, non-empty-but-noise delta) vs verify-and-keep (zero delta).
- **Question for spec author:** The spec asserted the mirror was "stale" / "DIFFERS"; the executor's verification found the S-BS-28 drift was **mechanical only (imports/path), not logical**. Should S-BS-28 / spec §5:158 be re-worded from "stale, do not trust" to "mechanically-transformed; verify byte-identity to `493b533` modulo imports"?
- **Recommended resolution:** OPEN-QUESTION (record-keeping). The deliverable's **intent** (bench IP ≡ `493b533` modulo transform) is independently verified true; "refresh" by verification is defensible and produces the identical end state. Closing S-BS-28 (session log `seams_closed`) is justified.

**Findings:**

- `[OPEN-QUESTION]` S-BS-31 invariant-#4 collision under v2-only (Ambiguity 1) — **high priority; recommend it gate WS-6c-AGENTIC.**
- `[OPEN-QUESTION]` Admissibility lint does not enforce owner-residency (Ambiguity 2).
- `[OPEN-QUESTION]` S-BS-28 / §5:158 wording: "stale" overstates a mechanical-only drift (Ambiguity 3).

---

## Summary of findings

| # | Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|---|
| 1 | Surface fidelity | 0 | 2 | 0 |
| 2 | Behavioral fidelity | 0 | 0 | 0 |
| 3 | Out-of-scope intrusion | 0 | 2 | 0 |
| 4 | Spec ambiguity surfaced | 0 | 0 | 3 |

**Total BLOCKING: 0** → cycle MAY close.

---

## Required actions (if any)

No BLOCKING findings; no required corrections before close.

NON-BLOCKING / OPEN-QUESTION dispositions:

1. **S-BS-31 (OPEN-QUESTION, high):** keep open; **promote to a gate on WS-6c-AGENTIC**. Resolution = spec-author decision (reassign v2-trio owner for the 3 codes, or ratify corroboration-only escalation). Owner: spec author / council IP owner.
2. **Lint owner-residency gap (OPEN-QUESTION):** log as a new seam (lint-hardening); pair with the S-BS-31 decision. Owner: monitor.
3. **S-BS-28 / §5:158 wording (OPEN-QUESTION):** re-word "stale" → "mechanically-transformed; verify byte-identity". Owner: spec author, next plan touch.
4. **Driver §2:71 "5 AZURE_*" → "4"; §1/§2 `JUDGES_V2` citation (NON-BLOCKING):** correct driver text. Owner: monitor.
5. **Stale commit hash in session log (`6bae3c0`→`c25510f`) + `c25510f` body "FABRICATED_ALLERGY"→"FABRICATED_HISTORY" (NON-BLOCKING):** refresh the hash at close; optionally amend the commit body wording. Owner: monitor/executor at close.

---

## Critic discipline self-check (inline mode)

- [x] Read the spec (§5/§6/§Ratification + topology §WS-6c) **cold, before** reading the executor's session log.
- [x] Reconstructed the diff via `git show`/`git diff` against the commits — and **independently reproduced** the A2 port-fidelity diff vs `493b533` and **re-ran** the A3 oracle (16 passed) — not via the executor's prose.
- [x] Each finding cites spec/driver file:line AND implementation file:line.
- [x] Did NOT edit any code, spec, or driver during this pass.
- [~] **Inline-mode caveat (HARD-GATE):** this is the monitor session, not a fresh isolated critic, and it read the driver during pre-flight (per the inline command's ordering). The load-bearing independence — forming an own read of spec + diff, and verifying A2/A3/S-BS-31 from source *before* anchoring on the session log — was preserved. For a contract-bearing safety-IP port, a fresh-critic session (`KICKOFF_CRITIC.md`, range `fb775f4..HEAD`) remains the stronger gate and may be run as confirmation if desired; the user elected inline (driver §168).

---

## Appendix: commits audited

```
c25510f test(council-port): offline consensus oracle (16) + gated live Azure smoke
a6e5b86 fix(taxonomy): derive production_judges from v2 config (S-BS-30) + re-snapshot @493b533
12281e1 feat(council-port): v2 council Mongo-free, importable + verified vs 493b533
```

## Appendix: files changed (`git diff --stat fb775f4..HEAD`)

```
lithrim_bench/runtime/council/__init__.py          |  54 ++
lithrim_bench/runtime/council/settings.py          | 347 +------
lithrim_bench/runtime/council/tests/__init__.py    |   0
lithrim_bench/runtime/council/tests/conftest.py    |  51 +
lithrim_bench/runtime/council/tests/test_consensus.py   | 265 +++++
lithrim_bench/runtime/council/tests/test_live_smoke.py  | 102 +++
pyproject.toml                                     |  12 +-
scripts/snapshot_taxonomy.py                       |  29 +-
taxonomy/taxonomy_snapshot.json                    |   5 +-
tests/test_taxonomy.py                             |  11 +-
10 files changed, 565 insertions(+), 311 deletions(-)
```

## Appendix: independent verifications run during this critique

```
# A2 port-fidelity (target vs lithrim-backend@493b533), context-0 diff:
compliance_council.py : 6 import lines + _ROLE_PROMPTS_DIR:457  (no logic change)
safety_flags.py       : byte-identical (diff exit 0)
llm_provider.py       : 1 import line
phi_redaction.py      : 1 import line
council_roles/*.txt   : all 5 identical (risk/policy/faithfulness/behavior/source_message)
line counts           : 2733/2733, 647/647, 147/147  (bench == backend)

# A3 offline oracle, debuglithrim 3.10.15, no network:
pytest runtime/council/tests/test_consensus.py -> 16 passed in 0.31s

# Owner-orphan (S-BS-31) from ported _TIER1_OWNERS:232-249 + re-snapshot:
production_judges = [risk_judge, policy_judge, faithfulness_judge]
MISSING_ALLERGY  = {behavior_judge, source_message_judge}   # orphaned
FABRICATED_CONSENT = {behavior_judge, source_message_judge} # orphaned
VALUE_MISMATCH   = {behavior_judge}                          # orphaned
examples/proof_case.jsonl uses MISSING_ALLERGY (x3), VALUE_MISMATCH (x3)

# Lint scope: lint_golden_against_taxonomy.py enforces D1 + D8 only (not owner-residency)
# seed_ontology.py:34 — invariant-#4 is a deferred "WS-4 scoring-time rule"
```
