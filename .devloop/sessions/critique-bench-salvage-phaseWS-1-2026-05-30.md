# Spec-Adherence Critique — `bench-salvage` phase `WS-1`

> Inline-mode critique (monitor self-audit), committed alongside close-out as
> `.devloop/sessions/critique-bench-salvage-phaseWS-1-2026-05-30.md`.

## Metadata

- **Stream:** `bench-salvage`
- **Phase:** `WS-1` (SQLite config plane + ontology data model)
- **Driver bundle:** `bench-salvage-phaseWS-1-sqlite-config-plane-driver`
- **Commits audited:** `6f4612f..0c73ff0` (8 code/test; `6d26a4e` = session-log commit, excluded)
- **Spec(s) read against:** `.devloop/prompts/bench-salvage_phaseWS-1_sqlite_config_plane_driver.md` §2/§4/§5; `.devloop/tasks/TASK_PACK_bench-salvage.json` task WS-1; `CLAUDE.md` §"Taxonomy snapshot is the contract"
- **Critique mode:** `inline` (monitor self-audit)
- **Reviewer:** monitor session

---

## Verdict

**NON-BLOCKING FINDINGS**

WS-1 lifts the WS-0 hardcoded spine into an ontology data model + a SQLite config plane with high fidelity: the three load-bearing behaviors (config-driven run reproduces the WS-0 grounded result; the ontology is the single source with the med-contract's extraction strategy and severity thresholds *as data*; doc-shim collections with recorded rationale) each trace driver → test → impl with a closing chain, and `test_no_hardcoded_constants_remain_in_harness` plus `test_presence_check_honours_declared_params` actively prove the de-hardcoding rather than asserting nearby. All surface deviations are additive/sensible. The one load-bearing open-question: the ontology seeded 23 flags from the council's `safety_flags.py`, but **4 of them are absent from `taxonomy/taxonomy_snapshot.json`** — which `CLAUDE.md` designates as *the* contract — so the harness now has two flag-source-of-truth surfaces that WS-2 must reconcile before the ontology drives grading. Zero blocking drift. (Separately: the two CITATION-DRIFTs the executor flagged are mine to fix at close.)

---

## 1. Surface fidelity

| Spec definition (driver §2) | Implementation | Match? | Severity |
|---|---|---|---|
| §2.1 ontology model `FlagDefinition / JudgeQuestion / VerificationContractDecl` | [ontology.py:38/50/57](../../lithrim_bench/harness/ontology.py#L38) + `SeverityMap` (:66) + `Ontology` (:91) + `load_ontology` | + `SeverityMap` (Q4.2 as data) | NON-BLOCKING (additive) |
| §2.3 `EvalProfile {judges, council_config, ontology_ref, tools, kb_bindings, severity_map}` | [config.py:45](../../lithrim_bench/harness/config.py#L45) — `severity_map` → **`severity_map_ref`** + added `ontology_path` | ref not embedded; +path | NON-BLOCKING |
| §2.3 `load_agent(name) -> Agent` | [config.py:148](../../lithrim_bench/harness/config.py#L148) exact (+`save_agent`/`seed_config_db`) | match | — |
| §2.4 4 doc-shim collections | [collections.py](../../lithrim_bench/harness/collections.py) (`conversation_item/conversation_session/call_kpi/compliance_report`) | match | — |
| §2.5 `ground(result, case)` reads ontology | [grounding.py:165](../../lithrim_bench/harness/grounding.py#L165) `ground(result, case, *, ontology=None)` | + optional `ontology` kwarg | NON-BLOCKING |
| §2.5 contract = declaration + executor | `VerificationContractDecl` (ontology) + `PresenceCheck(decl)` + `_CONTRACT_EXECUTORS` map ([grounding.py:94/155](../../lithrim_bench/harness/grounding.py#L94)) | match (design-decision 4) | — |
| §2.7 runner driven from config | [run_eval.py](../../scripts/run_eval.py) canonical + `run_ws0.py` shim (R3 deviation, approved) | match | — |
| §2.8 S-BS-9 normalization | [picklist.py:81/92](../../lithrim_bench/picklist.py#L81) `normalize_expected_verdict` + `expected_block` + documented collision order (:52) | match | — |

**Findings:**

- `NON-BLOCKING` `EvalProfile.severity_map` became `severity_map_ref` + an added `ontology_path` ([config.py:53/50](../../lithrim_bench/harness/config.py#L50)). Sensible — the severity map lives in the ontology (single source); the profile holds a reference. Not a contract break.
- `NON-BLOCKING` `SeverityMap` dataclass + `ground(..., ontology=None)` kwarg are additive over the driver's looser naming. The `SeverityMap.rescore` docstring explicitly states it "reproduces the WS-0 `_rescore` disposition exactly" — good provenance.

No renames that break a caller; the WS-0 `run_ws0.py` survives as a shim over the same single `run()` core (no second grounding path).

---

## 2. Behavioral fidelity

### Behavior 1: config-driven run reproduces the WS-0 grounded result (A1)

- **Spec assertion:** driver §5 A1 — "driven entirely from SQLite config … reproduces the WS-0 grounded result (MED FP suppressed, FABRICATED_HISTORY retained, composite reject)."
- **Test:** [test_ws1.py:76](../../tests/test_ws1.py#L76) `test_config_driven_run_reproduces_ws0` — `run_eval.py --agent ws0_default` (no `--case/--baseline/contracts`), asserts `verdict: reject` + `MEDICATION_NOT_IN_TRANSCRIPT -> SUPPRESSED`; + `test_config_roundtrip_through_sqlite` (:56) + `test_seed_config_db_builds_committed_agent` (:67).
- **Implementation:** `config.load_agent` → `run_eval` reads the profile/dataset → `grounding.ground(result, case, ontology=load_ontology())`.
- **Chain closes?** **YES.** The run is config-sourced end-to-end; the WS-0 outcome reproduces.

### Behavior 2: ontology is the single source; contract params + severity are data (A2 / Q4.2 / Q4.3)

- **Spec assertion:** driver §5 A2 — "ontology is the single source … no hardcoded constants … med presence-check present as a `verification_contract` declaration with explicit extraction params."
- **Test:** [test_ws1.py:109](../../tests/test_ws1.py#L109) `test_ontology_is_single_source_for_contracts_and_severity` (contract params + `severity_map.rescore` from data) + [:129](../../tests/test_ws1.py#L129) `test_no_hardcoded_constants_remain_in_harness` (`WS0_CONTRACTS`/`SEVERITY_WEIGHT`/`ws0-hardcoded/0` absent) + [:138](../../tests/test_ws1.py#L138) `test_presence_check_honours_declared_params` (a stricter `token_min_len` flips the same case from disproved→not-disproved).
- **Implementation:** [grounding.py:176](../../lithrim_bench/harness/grounding.py#L176) builds contracts from `ontology.contracts`; `PresenceCheck.__init__` reads `decl.params` ([:104](../../lithrim_bench/harness/grounding.py#L104)); `clinical_v1.json` carries the full param set + `severity_map {block_at_or_above:0.5, warn_above:0.0}`.
- **Chain closes?** **YES — and strongly.** `test_presence_check_honours_declared_params` is the load-bearing one: it proves the extraction strategy is genuinely data-driven (a config change changes behavior), not a constant relabeled. Q4.3 (extraction params explicit) and Q4.2 (severity thresholds as data) are closed.

### Behavior 3: doc-shim collections with recorded rationale (A3 / S-BS-4)

- **Spec assertion:** driver §5 A3 — "S-BS-4 doc-shim applied with rationale recorded."
- **Test:** [test_ws1.py:193](../../tests/test_ws1.py#L193) `test_doc_shim_collections_roundtrip` (4 named collections round-trip) + [:210](../../tests/test_ws1.py#L210) `test_doc_shim_rationale_recorded` (docstring contains "doc-shim" AND "relational").
- **Implementation:** `collections.py` — 4 single-JSON-column tables.
- **Chain closes?** **YES.** Rationale is asserted present, not just assumed.

All three chains close; the de-hardcoding is *demonstrated*.

---

## 3. Out-of-scope intrusion

Diff (`6f4612f^..6d26a4e`) = the §2 deliverables + 2 disclosed deviations:

- `report.py` (4 lines: `composite` reads `grounded.weights` after the `SEVERITY_WEIGHT` removal) — APPROVED-AT-PLAN, a necessary A2 consequence.
- `tests/test_ws0.py:103` (one removed-sentinel assertion `ws0-hardcoded/0` → `clinical/1`) — APPROVED-AT-PLAN, pre-authorized.
- No `../lithrim-backend/` edits. **No live `runtime/` import on the eval path** — re-verified: the only `runtime` token in the eval modules is the `ontology.py:8` docstring; `seed_ontology.py` light-imports the pydantic-only `safety_flags` and AST-parses the rest. Seed-not-import held.
- No WS-2 (`PipelineRequest` injection), WS-3 (mid-loop/JUTE/KB), or WS-6 scope. No drive-by formatting.

**No unauthorized intrusion.**

---

## 4. Spec ambiguity surfaced (OPEN-QUESTIONs)

1. **`OPEN-QUESTION` (load-bearing) — the ontology has two flag-source-of-truth surfaces; 4 flags are outside the canonical taxonomy.** `seed_ontology.py` sources 23 flags from `runtime/council/safety_flags.py` `SAFETY_FLAG_DEFINITIONS`, but `FABRICATED_CONSENT_SCOPE`, `MALAFFI_CODE_PROPAGATION`, `MISSING_DUAL_CODING`, `WRONG_PATIENT_INFO` are **absent from `taxonomy/taxonomy_snapshot.json`** (verified: present in the council source, absent from the snapshot's `tiers`). `CLAUDE.md` §"Taxonomy snapshot is the contract" designates the snapshot as *the only coupling point* / contract-of-record. The driver §2.1 pointed the seed at the council source, so the executor followed the driver and handled the orphans correctly (`tier=null`, surfaced in `diagnostic_stats`) — but **this is a spec-silent fork**: which is the ontology's authoritative flag set? For WS-1 it's inert (the WS-0 case uses only in-snapshot flags). **For WS-2, when the ontology drives grading, it must be reconciled** — either backfill the 4 into the snapshot, or have the seed treat `taxonomy_snapshot.json` as the tier/owner/membership authority and the council source only for prose definitions. Surface to the WS-2 spec author.

2. **`OPEN-QUESTION` — `owner_roles` is `_TIER1_OWNERS`-only (8 of 23 flags), `[]` for the other 15.** [session-log diagnostic] The executor deliberately did not merge the role-file "CODES YOU MAY RAISE" eligible-raiser lists. That is a defensible single-judge-BLOCK-ownership semantics, but it means the Q4.1 role-aware-calibration goal (WS-4) can only compute a role-aware "correct" predicate for 8 flags; the other 15 have no owner. **WS-4 must decide** whether calibration ownership = `_TIER1_OWNERS` (authoritative BLOCK ownership) or the broader eligible-raiser set. Recorded now so the WS-4 gate spec picks deliberately.

3. **`OPEN-QUESTION` (minor) — `resolve_case_fixtures` still returns the n10 row first on a `case_id` clash.** S-BS-9 normalized the *shape* and `load_case` lets a caller pin a source ([picklist.py:52](../../lithrim_bench/picklist.py#L52) documents the deterministic order), which is the right fix. But a caller using the bare `resolve_case_fixtures` without pinning still silently gets the n10 shape. NON-BLOCKING (documented + the normalizer makes shape irrelevant), noted so a future pack-hygiene cycle considers whether n10-first is the right default precedence.

(For the record, not Q4 findings: the two CITATION-DRIFTs in driver §1/§5 — "24 flags"→23, "5 role files"→3 — are confirmed monitor authoring errors and are fixed at `/devloop-close-phase`, per the executor's session-log flag.)

---

## Discipline self-check

- [ ] **Read the spec without reading the session log first** — **NOT fully met (known inline-mode limitation).** This ran in the same monitor session as the prior `/devloop-audit`, which read the session log. Per CRITIC persona, inline mode forfeits the strict no-prior-context property; WS-1 is a routine cycle (no spec/API-contract/public-launch touched), so inline is sanctioned. **Evidence of independent read:** this pass elevated the 4-untiered-flags item from the session log's benign framing ("defined but outside KNOWN_TAXONOMY_CODES") to a load-bearing WS-2 reconciliation open-question by cross-reading it against `CLAUDE.md`'s taxonomy-is-the-contract invariant — a finding the executor did not draw.
- [x] **Each finding cites spec file:line AND impl file:line.**
- [x] **No code/spec/driver edits made during this pass.** (The two citation-drift fixes are deferred to close-phase.)

---

## Findings summary

| Question | BLOCKING | NON-BLOCKING | OPEN-QUESTION |
|---|---|---|---|
| 1 Surface fidelity | 0 | 2 | 0 |
| 2 Behavioral fidelity | 0 | 0 | 0 |
| 3 Out-of-scope intrusion | 0 | 0 | 0 |
| 4 Spec ambiguity surfaced | 0 | 0 | 3 |

**Verdict: NON-BLOCKING FINDINGS.** Cycle may proceed to `/devloop-close-phase`. Carry Q4.1 (taxonomy flag-source reconciliation) into the WS-2 driver as an explicit pre-condition; Q4.2 (owner-roles semantics for calibration) into WS-4; Q4.3 (n10-first default) into a future pack-hygiene note. Fix the two CITATION-DRIFTs (driver §1/§5 + index.json re-verification log) at close.
