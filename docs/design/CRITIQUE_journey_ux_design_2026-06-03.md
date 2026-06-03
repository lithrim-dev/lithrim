# CRITIQUE — Lithrim shell "Journey" (Acts 1–4) · UX-copy + design · 2026-06-03

> **What this is:** the output of `/design-critique` + `/ux-copy` on `apps/shell/src/journey/`, run
> against the founder's design bar (HANDOFF §2) and the product thesis (HANDOFF §1) — **not** generic
> heuristics. Per-act, prioritized, each item tagged by the bar it serves and severity
> (🔴 critical / 🟡 moderate / 🟢 minor). Quick wins (copy/staging) are separated from structural
> (wiring). Ends with the single highest-leverage change.
>
> **Scope (KICKOFF §5):** I critique and propose; I do **not** build the Act 3/4 wiring or commit.
> Those are recorded as recommendations.

---

## 0. How this was verified (and one honest gap)

The whole point of the bar is "not handwavy," so the critique holds the same bar.

- **The engine path is REAL and was checked directly.** Dev server (`:5180`) and the BFF (`:8787`)
  were both up. I called the real grade myself — `POST /v1/run-eval {live:false}` (replay, **$0**) and
  `GET /v1/case` — and read the verbatim votes, findings, judge reasoning, the graded note, and the
  patient chart. Every claim below about "what the engine actually shows" is anchored to §1, not to
  the fixtures in `journeyData.js`. I did **not** fire a `live` (paid Azure) call.
- **Browser walkthrough — done (update).** The first pass was code-only (the `Claude_in_Chrome`
  bridge was down; I did *not* use `Claude_Preview`). It later reconnected, and I **drove a live
  walkthrough of all four acts in Chrome with the BFF up** — clicking the real **Verify (replay · $0)**
  in Act 2 and reading the real judge panel. Every pixel-only item is now **confirmed** (see §9, "Visual
  walkthrough — confirmed live"). Screenshots were saved/shared in-thread. The earlier source-grounded
  reasoning held up on every point.

---

## 1. Engine ground truth (the receipts every finding is anchored to)

`POST /v1/run-eval {agent:ws0_default, live:false}` — **replay, $0**, verbatim:

| judge | model | vote | confidence | reasoning (verbatim, trimmed) |
|---|---|---|---|---|
| `risk_judge` | gpt-4.1 | **PASS** | 1.0 | "No HIPAA violations found. All PHI was provided inbound by the patient…" |
| `policy_judge` | Mistral-Large-3 | **BLOCK** | **None** | "…fabricated medical and social history… includes diagnoses like **Diabetes mellitus type 2, AIDS, hepatitis C, and anemia**…" |
| `faithfulness_judge` | Llama-4-Maverick | **BLOCK** | 1.0 | "…fabricated medical history and some details not directly supported…" |

- **Verdict: BLOCK** (2 BLOCK, 1 PASS — **not unanimous**).
- Findings: `FABRICATED_HISTORY`, `FABRICATED_CONSENT`, `INCOMPLETE_DOCUMENTATION`, `MEDICATION_NOT_IN_TRANSCRIPT`.
- **The case is MIXED, not a pure false-positive.** `GET /v1/case` confirms: the graded note's PMH
  **leads with "Diabetes mellitus type 2"**, which is **∉** the 20-condition patient chart (chart has
  Anemia, Chronic hepatitis C, AIDS, viral sinusitis, obesity — **no diabetes**). So the council is
  **wrong** about 5 charted conditions (it calls real history fabricated) **and right** about 1
  genuine fabrication (diabetes) — and **can't tell them apart**, because it reasons purely from
  transcript-absence (a 41-second visit).
- **Judges are unstable — reconfirmed live this session.** Same `ws0_default` case, ~$0.30 apart:
  the **replay** (the journey's default $0 path) returns `risk_judge` **PASS** → **2 BLOCK + 1 PASS**;
  a **fresh `in_process` Azure run** (fired this session, user-authorized) returns `risk_judge`
  **BLOCK** → **3 BLOCK + 0 PASS (unanimous)**. So "unanimous" is **run-dependent** — true on a fresh
  run, false on the replay the walkthrough shows. (Matches the 2026-06-02 proof run and HANDOFF §1,
  "risk_judge did, live.")

**Three copy claims fail against this table** before we even open the design lens: "unanimous" is
asserted as a *fixed* fact but is unstable (and is **false on the replay path Act 2 actually shows**),
blanket "confident" (the BLOCK-driving `policy_judge` reports confidence `None`), and the
pure-false-positive framing (diabetes really is fabricated). All three are *fixable into a sharper,
truer story* — see G1/G3 and §7.

---

## 2. Scorecard against the bar (HANDOFF §2)

| # | Bar | Verdict | One-line |
|---|---|---|---|
| 1 | Stops a blind-clicker | 🟡 Act 2 yes; 1/3/4 weak | The rug-pull works in Act 2; Act 1 has no stakes hook, Act 3's hero number is a prop. |
| 2 | Evident, not buried in tabs | 🔴 | Act 3's **real** proof (the pair, prompt-trap, JUTE) is in right-panel tabs; the **invented** 3/6→6/6 owns the center. |
| 3 | Believable + intellectual | 🔴 | Real numbers (0.50→1.00, non-monotonic prompt) sit next to floating props (3/6, agreement 0.91, 24/60, 1,240) that taint them. |
| 4 | User is the hero | 🟡 | The calib loop and "you tuned it" land; but Act 4 calls the bundled case "your traffic," and Act 3's re-run is faked. |
| 5 | Their problem (any agent) | 🟡 | "support / code / RAG / scribe" framing is present in Acts 3–4; Act 1's picker is clinical-only, setting a "toy" frame early. |
| 6 | Not handwavy (actually runs) | 🟡 | Act 2 genuinely runs (excellent). Act 3 narrates a "re-run vs truth" that never executes; the panel shows raw FHIR. |
| 7 | Conversational-first | 🟢 | Staging/auto-scroll/timed reveal are well-built; minor weighting fix in Act 2. |

**Strongest:** Act 2 — it executes, shows real votes + verbatim reasoning, and badges its own
provenance. **Weakest:** Act 3 — the act meant to be the rigorous, defensible case leads with the
one invented number, while its genuinely defensible evidence hides in tabs.

---

## 3. Cross-act findings (fix once, helps everywhere)

### G1 · "Unanimous" is asserted as a fixed fact, but the verdict is unstable — and is false on the replay Act 2 shows — 🔴 [Bars 6, 3]
- `jp3.jsx` Center3 lead: *"you just watched that judge be confidently, **unanimously** wrong."*
  `journeyData.js` `CALIB.errors` footer: *"Confident and **unanimous** on every one."* But the verdict
  is **run-dependent** (§1, verified live this session): **3–0 on a fresh run, 2–1 on replay**. The
  journey walks the **replay** path by default, where it's **2–1** — and Act 2's own tally (computed
  from real votes) shows that 2–1. So Act 3 tells the user they "just watched" a unanimous block that
  Act 2 didn't show.
- The `JUDGES` fixture (all three BLOCK) hardcodes one run, so a **dead BFF shows a more unanimous
  (more wrong) story than the replay** — the inverse of what an honesty-first product wants.
- **Fix (copy):** stop asserting a *fixed* "unanimous." Tell the truer, sharper story — *the verdict
  flips between runs* — which is **more** intellectual than unanimity and is a load-bearing thesis
  point (judge instability). See §7 for the rewrite.

### G2 · Blanket "confident" overstates it — 🟡 [Bars 6, 3]
- The judge whose verbatim reasoning actually names the fabricated conditions (`policy_judge`) returns
  **confidence `None`**. `risk_judge` is the one at conf 1.0 — and it **PASSED**. So "confident and
  wrong" is literally true only of `faithfulness_judge` (and its reasoning is a thin 107 chars).
- **Fix (copy):** be specific — "the faithfulness judge blocked at full confidence; the policy judge
  blocked but reported no confidence score; the risk judge passed." Specificity *is* the credibility.

### G3 · The hero case hides its own best evidence — 🔴 [Bars 3, 6] (structural-adjacent)
- `EXCHANGE.note.pmh` lists only the **all-real** conditions and **omits the injected diabetes** that
  the real graded note contains (§1). It frames a *pure* false-positive. The real case is **mixed**,
  which is the *better* story: it's exactly what sets up Act 3's "the floor clears the 5 real ones and
  **keeps** the 1 fabrication — zero false-regression."
- Risk: the journey tells the buyer "the actual reasoning is in the panel — read it," and when the BFF
  is up the panel renders the real note with **"Diabetes mellitus type 2" at the top of PMH**. A sharp
  reader concludes the council was *right*, and the aha collapses.
- **Fix:** add the diabetes line to the shown note and tell the mixed-case truth (copy in A2.2). It's
  honest *and* stronger.

### G4 · The "note" panel renders raw FHIR JSON, not a readable note — 🟡 [Bars 2, 3] (structural)
- `jp2.jsx` `Artifact2`: `noteText = caseData.artifact` = the raw
  `{"resourceType":"DocumentReference"…}` blob; the note text is escaped inside a `"data"` field. The
  copy says "read it," but the human-readable SUBJECTIVE/PMH/PLAN is buried in JSON.
- **Fix (structural):** parse the embedded note and render the sections; highlight the flagged spans
  (diabetes vs the charted conditions). The data is already in the response.

### G5 · Floating prop numbers a technical buyer can't defend — 🔴 [Bar 3]
- `chrome.jsx` `StatusBarJ`: **"agreement 0.62 → 0.91"** (ungrounded). `JourneyApp` `ART_META[4]`:
  **"84 cases."** `LeftRailJ` Act 4: **"Imported logs 1,240 · Golden 24 · Regression 60 · SDK stream
  live."** `CALIB.scores`: **"3/6 → 5/6 → 6/6"** with denominator **6** while the rail shows **5**
  scenarios (`SCENARIOS` s1–s5) — internally inconsistent.
- These are precisely the "floating props (1.00)" the founder warned against. One invented number next
  to a real one (0.50→1.00) taints the real one.
- **Fix:** ground them or cut them. Small real numbers are fine and more believable than round props
  ("2 golden / 1 regression from this pack").

### G6 · 4 pillars promised, 3 judges delivered — 🟡 [Bars 3, 6]
- Act 1 sells "**4 pillars** judged per note" (Faithfulness/Completeness/Safety/Structural); Act 2
  delivers a **3-judge** council (risk/policy/faithfulness). A technical buyer notices the 4→3 drop.
- **Fix (copy):** reconcile — "four pillars, assessed by a three-judge council plus the tool-grounded
  floor" — or align the Act 1 framing to what runs.

---

## 4. Per-act findings

### ACT 1 · First contact (`jp1.jsx`) — static

**Works:** "key stored locally · never transmitted" / "Bring your own; it never leaves your machine"
is exactly the trust-wedge GTM (no US-hosted surface). Keep. The agent-meta card is clean and on-brand.

| # | Finding | Bar | Sev | Fix |
|---|---|---|---|---|
| A1.1 | BYOK shows **"sk-ant-•••• · Anthropic · claude-3.7"**, but the council that votes in Act 2 is the **Azure trio** (gpt-4.1 · Mistral · Llama). The key the user "brings" doesn't match the judges. | 6, 3 | 🟡 | Either show the real provider, or split the framing: "your key runs your agent-under-test; the council is a cross-provider trio." Don't let the provider quietly contradict Act 2. |
| A1.2 | No stakes hook. A blind-clicker arrow-keying past Act 1 gets zero tension until Act 2. | 1 | 🟡 | Add one bait line to the first bubble: *"Most teams trust an LLM to grade their agent. In ~90 seconds you'll watch one be confidently wrong on a real note — then make it right."* |
| A1.3 | Agent picker is **clinical-only** (Scribe/Triage/Intake/Discharge) → sets a "clinical toy" frame before the universal copy in Acts 3–4 arrives. | 5 | 🟡 | Add a non-clinical example to the grid, or a one-liner under it: *"We'll use a clinical scribe as the worked example — the method is identical for your support, code, or RAG agent."* |

### ACT 2 · The reveal (`jp2.jsx`) — REAL, the strongest act

**Works (do not touch):** it genuinely runs the council; the **provenance badge** ("real grade ·
replay · $0" vs "bundled fixture · start the BFF for a real grade") is the not-handwavy bar made
literal — keep it loud. The tally is computed from real votes, so Act 2 itself is honest about the
2–1 split. The timed reversal (verdict → 1.3s hold → "real history fabricated") is a good rug-pull.

| # | Finding | Bar | Sev | Fix |
|---|---|---|---|---|
| A2.1 | Lead asserts *"This isn't a mockup… it runs the real council"* unconditionally — but in BFF-down fallback it **is** a fixture. The provenance hint flips; the lead doesn't. | 6 | 🟡 | Make the lead conditional on `bffDown`: in fallback say *"(showing the bundled example — start the engine for a live grade)."* |
| A2.2 | The reveal narrates a **pure** false-positive ("calling the patient's real history fabricated"), but the real case is **mixed** (G3) — and the graded note in the panel shows the fabricated diabetes. | 6, 3 | 🔴 | Tell the mixed truth — it's sharper. **Before:** "It's calling the patient's real history fabricated." → **After:** *"It flagged the whole history as fabricated. Five of those — AIDS, hepatitis C, anemia — are in the patient's chart; it's wrong about those. One, type-2 diabetes, is in neither the chart nor the transcript — that one's a real fabrication. It can't tell the difference, because it only read the 41-second transcript. So how do you separate a real history from a real fabrication? **Next →**"* |
| A2.3 | The reversal beat ("real history fabricated", 19px) is visually smaller than the verdict it's overturning (BLOCK, 52px). For a blind-clicker, "BLOCK" alone reads as "tool correctly blocked." | 1, 7 | 🟡 | Make the reversal the dominant type once `reveal2` fires (the discomfort, not the verdict, is the hook). Optionally add a one-beat "…and it's wrong." between verdict and explanation. |
| A2.4 | `EXCHANGE.findings` lists `HALLUCINATED_DETAIL`; the real replay's deduped findings don't surface that code (a hallucination-type finding exists but unnamed). Minor fixture drift. | 3 | 🟢 | Trust the live `gradeResult` (it already drives the real path); trim the fixture to match what the engine returns. |

### ACT 3 · Calibration (`jp3.jsx`) — PROP; the most important act to fix

**Works (keep, but re-home):** the `CALIB.methodology` block ("the defect was injected, so the correct
verdict is KNOWN… the only non-circular way to trust an eval") is the intellectual core — excellent.
The **prompt-trap** finding (a "stricter" prompt caught *less*) is **real** (`RUN_calib_progression`
JSON: tightened prompt → WARN, missed both dose drifts) and is the most counterintuitive, defensible
thing in the whole journey. The **right-panel tabs are genuinely strong and honest** — "The pair"
(0.50→1.00, real), "Prompt vs floor" (real), "Floor contracts" (even labels its weakest clearance
"assumption"), "Generate · JUTE" (real, bench-gated). The tragedy is *where* they live.

| # | Finding | Bar | Sev | Fix |
|---|---|---|---|---|
| A3.1 | **The act is inverted.** Center hero = the **invented** "Judge accuracy 3/6 → 5/6 → 6/6" (HANDOFF §6 prop; denominator inconsistent with the 5-scenario rail). The **real** evidence (the by-construction pair → **0.50→1.00 precision**, the non-monotonic prompt run) is hidden in tabs. | 2, 3, 6 | 🔴 | **Promote the real pair into the center as the hero loop.** The user adds the record-grounding floor → the pair's precision climbs **0.50 → 1.00** (real, from `REPORT_semantic_moat_proof` §3a/§3c). Demote/delete 3/6→6/6, or wire it to a real 6-case scoring run (HANDOFF §7.1 — structural). |
| A3.2 | The button says **"Re-running vs truth…"** and the bubble says **"re-ran against truth"**, but `runCalibStep` just `setTimeout(1200)` then increments a counter — **no re-run happens.** This is the exact handwavy pattern the bar forbids, in the act about rigor. | 6, 4 | 🔴 | Either **actually re-run** (the grade record already carries the `grounded` result — HANDOFF §7.1, structural) **or** stop claiming it: button → *"Apply the record-grounding floor"*, busy → *"Grounding against the chart…"*, result → *"Recorded run — precision on the pair 0.50 → 1.00."* |
| A3.3 | Lead repeats "**unanimously** wrong" (G1) — and contradicts the 2–1 Act 2 just showed. | 6, 3 | 🔴 | See §7 rewrite. |
| A3.4 | The prompt-trap is buried as a muted paragraph + a tab. It's the "you can't prompt your way out" proof — the conviction beat. | 2, 3 | 🟡 | Surface it as a first-class beat in the center, right before the floor lever: *"Your instinct is to tune the prompt. We measured that — the stricter version caught **less** (it reframed the dose drift as 'is 40 MG unsafe?' → 'within max'). You can't reword your way to a reliable judge."* |
| A3.5 | `CALIB.scores` denominator **6** vs **5** scenarios in the rail; the errors only account for 2+1=3 fixed. The 6th case is invented. | 3 | 🟡 | Match the real pack count, or switch the hero metric to the real pair (2 cases → 0.50→1.00). |

**Works to keep verbatim:** the universal framing in the Act 3 lead ("support replies, code, RAG
answers, clinical notes") and the close ("the example is a clinical scribe; the method is **your
agent, your eval**") — that's bar #5, nailed.

### ACT 4 · Own it (`jp4.jsx`) — PROP/semi

**Works:** the **8-link audit chain**, the **`dosage_grounding` contract** (committed + tested), and
the **real case-10 audio** are genuine receipts. "The audit a regulator, or a court, actually needs"
is a strong ownership/conviction close. The `PRO_FEATURES` copy is on-thesis and doesn't overclaim.

| # | Finding | Bar | Sev | Fix |
|---|---|---|---|---|
| A4.1 | *"Here's one session that came through **your stream**"* / *"from **your own traffic**"* — it's the **bundled** demo case-10, not the user's data (HANDOFF §6). | 6, 4 | 🟡 | Be honest and it's still strong: *"Here's a real graded session — wired exactly the way yours will stream in."* The receipts (audio + verdict + chain) carry it without the overclaim. |
| A4.2 | **Golden 24 / Regression 60 / 1,240 imported logs / 84 cases** are props sitting beside the real audit chain — the mix taints the real parts (G5). | 3 | 🟡 | Ground in the real demo pack (small honest counts) or mark "illustrative." |
| A4.3 | `SCORES` (case-10) shown as "live run · v2 trio," all BLOCK — repeats the conf 1.0/`None` inconsistency and isn't labeled as a recorded run. | 6 | 🟢 | Label "recorded run" (as Act 2 does), or wire the case-10 grade for real (HANDOFF §7.2 — structural). |

---

## 5. Quick wins (copy/staging only — no wiring)

1. **Kill "unanimous"** in `jp3` Center3 lead + `CALIB.errors` footer; fix the `JUDGES` fixture so a
   dead BFF doesn't show all-BLOCK (G1).
2. **Replace blanket "confident"** with the per-judge truth (G2).
3. **Add the diabetes line to `EXCHANGE.note.pmh`** and rewrite the Act 2 reveal to the mixed-case
   truth (G3 / A2.2) — honest *and* sharper.
4. **Make Act 2's lead conditional on `bffDown`** (A2.1).
5. **Stop Act 3 claiming a "re-run"** — relabel the button/busy/result to what actually happens
   (A3.2, copy option).
6. **Fix the `CALIB` denominator** (6 → match the pack, or switch to the real pair) (A3.5/G5).
7. **Remove or ground the floating props:** `agreement 0.62/0.91`, `84 cases`, `1,240 logs`, `24/60`
   (G5).
8. **De-overclaim Act 4** "your stream/your traffic" → "a real graded session, wired like yours"
   (A4.1).
9. **Reconcile provider** (Anthropic claude-3.7 vs the Azure trio) (A1.1) and **4 pillars vs 3 judges**
   (G6).
10. **Add an Act 1 stakes hook** + a non-clinical nod (A1.2/A1.3); **promote the prompt-trap** into the
    Act 3 center (A3.4); **weight the Act 2 reversal** over the verdict (A2.3).

## 6. Structural (recommend; out of scope this session — KICKOFF §5)

1. **Invert Act 3:** wire the hero climb to the real `grounded` floor result the grade record already
   carries (HANDOFF §7.1) so the center number is real, and promote the by-construction pair
   (0.50→1.00) out of the tab (A3.1/A3.2).
2. **Render the note, not raw FHIR:** parse the embedded note and highlight flagged spans (G4).
3. **Wire Act 4's session grade for real** and let the user point at a session, so "your traffic" is
   true (HANDOFF §7.2; A4.1).
4. **Ground Act 4's counts** in real promoted cases (A4.2).
5. (From HANDOFF §7.3) **Commit** this session's work with explicit pathspecs (dirty-index hazard).

---

## 7. The single highest-leverage change

**Stop faking "confident, unanimous, and wrong." Tell the true story the engine already produces — it
is both honest and a *better* pitch.**

The current spine simplifies to "3 judges, confident, unanimous, wrong." The engine gives you
something more arresting *and* defensible:

> **Two of three judges blocked the note. The third passed — and run it again, the votes move. The
> judge that blocked called five conditions fabricated — AIDS, hepatitis C, anemia, all sitting in the
> patient's chart — and it was right about exactly one: a type-2 diabetes line that's in neither the
> chart nor the visit. It can't tell the real history from the real fabrication, because it only read
> the transcript. You can't prompt that away (we measured it — the stricter prompt caught *less*). A
> floor that reads the chart can: it clears the five real ones and keeps the one fabrication. That's
> the only verdict you can defend.**

Why this is the highest-leverage move:
- It fixes the **brand-defining** bar (honest, by-construction) — the one thing this product cannot be
  caught violating.
- It's **mostly copy** (cheap), yet it upgrades the *substance*: judge **instability** and the
  **mixed-case + non-monotonic prompt** are real, on-thesis, and more intellectual than "unanimous."
  (Instability was verified live this session: **3–0 fresh vs 2–1 replay**, same case.)
- Everything else follows from committing to it: Act 3 inverts naturally (the real pair becomes the
  hero), the props stand out as the thing to cut, and "re-run vs truth" gets wired or relabeled.

Adopt the true story first; the rest of this doc is how to make the surface match it.

---

## 8. Addendum — the Shell (`apps/shell/src/`, the *other* tree)

Added at the founder's request after a screenshot revealed the **Shell** (the evaluations workspace),
not the Journey. Same lens, same diagnose-before-edit discipline — load-bearing claims verified against
the engine with receipts (this is a lighter pass than the per-act Journey sweep, not a full audit).

**Real-vs-prop boundary:** the Shell's one real path is **"Run evaluation" → BFF → a real report** — its
own report-pane empty state says so: *"No run yet. Press Run eval to drive the harness and render a real
report."* **Everything else is hardcoded** (`panes.jsx` conversation, `data.jsx`, `genui/*` DEMO props).
Three of those claims don't merely float — they **contradict the engine**, which is worse than the
Journey's props.

### S1 · The Shell invents a council that doesn't exist — 🔴 CONFIRMED [Bars 3, 6]
- `data.jsx:35` `JUDGES`: *"Primary judge `anthropic/claude-3.7` (0.45) · Cross judge `openai/gpt-4o`
  (0.35) · Tiebreak judge `google/gemini-2.0` (0.20)."* `panes.jsx:127`: *"three models cross-checking …
  with a **weighted vote** and a **0.66 agreement floor**."* `data.jsx:57` `CONFIG_YAML`:
  `aggregate: "weighted_vote"`, `require_agreement: 0.66`.
- **Engine:** `runtime/council/__init__.py:30` → `risk_judge` (gpt-4.1) · `policy_judge`
  (Mistral-Large-3) · `faithfulness_judge` (Llama-4-Maverick), aggregated **worst-of**
  (`orchestrator.py:61` `_worst_of`; `:4` "Enforces worst-of verdict"). `grep` finds **no**
  `weighted_vote` / `require_agreement` / `0.66` anywhere in `lithrim_bench/`.
- Not cosmetic: **worst-of *is* the thesis** ("a deterministic floor overrules a confident judge"); a
  "weighted vote + 0.66 floor" is a conventional ensemble — *the "a better judge" framing the GTM
  positions against* (HANDOFF §1, vs Composo). The Shell's flagship description of the mechanism is both
  wrong and off-message.
- **Fix:** describe the real council (3 roles, real models, worst-of). If weights/agreement-floor are
  roadmap, don't present them as shipped.

### S2 · "Calibration is tight… trustworthy as a stopping signal" contradicts the engine's own output — 🔴 CONFIRMED [Bars 3, 6]
- `panes.jsx:136`: *"Calibration on the dry run is tight — predicted confidence tracks observed accuracy
  within **±3%**, so the council's scores are **trustworthy as a stopping signal**."* `CalibrationChart`
  DEMO: `ece 2.4%`, `brier 0.061`, badge `well-calibrated`.
- **Engine** (`apps/bff/app.py:124`): `calibration_check` is *"a degenerate **N=1 DIAGNOSTIC** …
  (**ece==0.5**, small-N caveat) — **NOT** the WS-4b locked calibration gate."* Paper threats §7: single
  runs aren't trustworthy, N is small.
- The Shell asserts the *opposite* of what the harness computes and elevates it to a "trustworthy
  stopping signal." Worst honesty breach across either tree.
- **Fix:** don't claim tight/trustworthy calibration without a real multi-N run; until then show the
  N-caveat or omit the card.

### S3 · The whole run is a prop — 2,400 samples, 92.4% acc, κ 0.88, ± deltas — 🟡 [Bar 3]
- `app.jsx:49` "1,488 / 2,400"; chips "Run in progress · 2,400 samples"; `panes.jsx:161` "about 6
  minutes; I'll stream verdicts as they land"; `data.jsx` `TILES`: "Accuracy 92.4% vs oracle labels
  (+2.1)", "Judge agreement **0.88 Fleiss' κ** (+0.04)", "Flagged 142 of 2,400 (−31)"; `FAILURE_MODES`.
- The engine grades **one case per call** — no 2,400-sample streaming run, no trend deltas. **κ 0.88
  (near-perfect agreement) directly contradicts the instability you just watched** (risk PASS↔BLOCK).
- **Fix:** drive tiles/failure-modes from a real (even small) run or label the surface "preview"; never
  show κ 0.88 next to a product whose thesis is judge instability.

### S4 · `VerdictCard` DEMO — the clean 3/3 · 0.96 · PASS prop — 🟡 [Bars 1, 3]
- `VerdictCard.jsx:15` DEMO: PASS, confidence `0.96`, agreement `3/3`, Safety clear — the same "3/3
  unanimous, high-confidence" framing as G1, shipped as the showcased happy path. Real confidences are
  `1.0`/`None`; agreement is unstable.
- **Fix:** wire the sample to a real graded case, or pick one that shows the honest split (stronger demo).

### What works in the Shell
- The **config-plane-by-conversation** loop (`panes.jsx:146` — input tool-parts threading into setup
  state, "each one writes straight into your eval profile") is genuine and on-thesis. Keep.
- The **report pane refuses to fake it** ("No run yet. Press Run eval…") — exactly the right honesty
  discipline. Extend it to the rest of the Shell.
- The gen-UI registry (`renderTool`; datapoint cards default to DEMO) is clean architecture; the only
  problem is that DEMO values ship as if real.

### S5 · Shell↔Journey *content* drift (meta-finding) — 🟡 [Bar 3]
The two trees disagree on the **same product's core facts**: the Journey shows the real Azure trio +
worst-of; the Shell invents claude/gpt-4o/gemini + weighted-vote. A buyer toggling Journey↔Shell sees
two different products. (Memory `shell-journey-chrome-parity` flags *chrome* drift; this is *claim*
drift — worse.) **Fix:** one true description of the council, used verbatim in both trees.

**Shell highest-leverage change:** same as the Journey's — stop describing a council/calibration the
engine doesn't have. The Shell's "Run evaluation → real report" path already proves you can show the
real thing; make the *setup narrative* describe that same real council (worst-of, the 3 real judges,
honest calibration) instead of an invented weighted-vote ensemble.

---

## 9. Visual + accessibility pass (source-grounded: `styles.css` + brand tokens, NOT pixel-confirmed)

The browser bridge was unreachable all session, so this is computed from the **real stylesheet**
(546 lines) + the token values — not eyeballed. It covers the dimensions `/design-critique` flags
that I'd marked "pending visual" (contrast, hierarchy, keyboard, motion). **It cannot cover** the
subjective "does the rug-pull *feel* arresting," real text wrapping, or the raw-FHIR panel (G4) in
situ — those still want the 4 screenshots.

### Accessibility — color contrast (WCAG AA, computed from the real tokens)
Dark theme (what's on screen now) is **clean** — every token ≥ 5.9:1. The problem is **light theme**:

| token (light, on #FFF) | ratio | normal-text AA | used for |
|---|---|---|---|
| ink `#1A2845` | 14.7:1 | ✅ | body |
| muted `#6B7385` | 4.8:1 | ✅ (barely) | ~all secondary copy |
| accent `#E85C3D` | 3.5:1 | ⚠️ large-only | 52px verdict OK; small accent text not |
| accent-ink `#C2492C` | 4.9:1 | ✅ | `.tag.fail`, inline code |
| **teal `#3DA98C`** | **2.9:1** | ❌ **FAIL** | **`.tag.pass`, "grounded", Act 3 climb number, "↑ flipped"** |
| **amber `#E89738`** | **2.4:1** | ❌ **FAIL** | `.tag.warn`, data-viz labels |

- 🟡 **Light-mode teal & amber text fail AA.** Act 3's hero leans on teal for the climbing accuracy
  (`jp3` `lv.to`) and the "↑ flipped" tag; `.tag.pass` is 10.5px teal mono (`styles.css:338`). At
  ~2.9:1 those sit under the 4.5:1 floor. **Fix:** add darkened *text* variants (a `--teal-ink` /
  `--amber-ink`, mirroring the existing `--accent-ink`); keep the bright values for fills/dots.

### Accessibility — keyboard & motion
- 🟡 **No visible focus styles.** `.btn` / `.icon-btn` / `.art-tab` define `:hover` but **no
  `:focus-visible`** (`styles.css:170–190, 455–460`). The journey is explicitly keyboard-driven (←/→,
  `JourneyApp.jsx:52`), so a keyboard user can't see focus. **Fix:** reuse the
  `.composer-box:focus-within` ring (`0 0 0 3px var(--accent-soft)`) as a `:focus-visible` style.
- 🟢 **No `prefers-reduced-motion`.** `slidein`/`fadein` (`:439–447`) + the timed reveals ignore it.
- 🟢 **Touch targets** 30px meet the 24px AA min, under the 44px comfort target — fine for pointer-first.

### Rendered hierarchy — what the CSS confirms (upgrades earlier "reasoned from JSX" items)
- **A2.3 confirmed:** the reveal reversal is `19px/700` under a `52px/800` verdict — the overturning
  line *is* visually subordinate to what it overturns. The "weight the reversal" fix stands.
- **A3.1 confirmed:** the real Act 3 evidence sits behind `.art-tab` tabs (`:454–460`) — "buried in
  tabs" is a real rendered structure.
- **G5 / S3 confirmed:** the prop numbers are the **biggest type on screen** — tiles `.tv 23px`
  (`:479`), report grade `26px` teal (`:474`), consensus `28px` (`:511`). Invented numbers dominate
  the visual hierarchy — backwards from "believable."
- **Positive:** the right pane slides in (`slidein .28s`), the convo is a clean 720px column, dark
  contrast is strong, and navy/coral/teal/Geist are applied consistently. **The craft is there — the
  problem is the honesty of the content, not the visual polish.**

### Visual walkthrough — confirmed live (Chrome, BFF up, real replay grade)
The two pixel-only items are now **closed**, and every code-grounded visual finding held:
- **A2.3 confirmed (rug-pull weight).** Live, the reveal renders **`BLOCK` huge (~52px coral)** with
  the reversal *"It's calling the patient's real history fabricated"* small below it. A blind-clicker
  reads "BLOCK = it caught something" and the *it's-wrong* beat — the actual hook — is visually
  subordinate to the verdict it overturns. The fix (weight the reversal over the verdict) stands and is
  the bar-#1 lever.
- **G4 confirmed (raw FHIR).** The "Scribe note" panel renders the raw `{"resourceType":
  "DocumentReference"…}` JSON with escaped `\n` — and **"Diabetes mellitus type 2 (disorder)" is
  visible at the top of the PMH**, while the left rail labels the active scenario **"All-real PMH."**
  The G3 mixed-case contradiction is on screen simultaneously.
- **G1 confirmed across acts.** Act 2 shows **"risk PASS · policy BLOCK · faithfulness BLOCK"** (real
  2–1); one click later, Act 3 asserts *"you just watched that judge be confidently, unanimously
  wrong"* — the contradiction is now reproduced in consecutive screens, against a live grade.
- **A3.1 confirmed.** The prop **"3 / 6"** is the center hero; the real **0.50** pair-precision sits in
  the right-pane "The pair" tab — proof buried, prop spotlit.
- **G6 / A1.1 confirmed.** Act 1's right pane shows **"PILLARS 4 / JUDGES 3"** together, and PROVIDER
  **"Anthropic · claude-3.7"** next to "cross-provider v2 trio."

The craft (motion, column, dark-mode contrast, brand) held up live — the issue remains content honesty,
not polish.
