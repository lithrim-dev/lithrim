# Proof — bench-salvage CHATBIND-2: the chat drives the artifact pane (2026-06-09)

> A-LIVE attestation. Env: :5180 shell / :8787 BFF / BYO-Claude (local `claude` CLI). **$0** — `$0`
> REPLAY only; the BYO-Claude cost figure (~0.14 + 0.17 subscription-equivalent for the two final
> turns) is **not** a per-call charge. No paid run, no Azure, no confirm gate touched.

## Claim
The conversational agent now **drives the 3rd pane by talking** — live, end-to-end. A plain-language
ask ("run a `$0` replay and show me the judge council") makes the BYO-Claude loop run the replay
itself, **open + focus the Judge council tab, and show THIS case's realized votes**; a follow-up
("show its config") **focuses the Config tab** on the active case's ontology. No human click on the
panel. CHATBIND-2 is attested live; the offline tests' stub becomes a real integration.

## What changed
- **Commits:** `e7b0806` (bff: `focus_artifact` tool + pane-control prompt + `run_result` lift),
  `4bf3c89` (shell: honor `tool-open_artifact` + lift into `runResult` + ConfigTab agent thread),
  `d8d9e70` (tests), `961140d` (session log). Branch `bench-salvage/ws6c-dspy` — **not pushed**.
- **Mechanism (3 load-bearing pieces):**
  1. A `$0` read-only **`focus_artifact({tab})`** tool emits a `tool-open_artifact` **directive**
     the shell honors (open+focus; rendered as a tiny non-card affordance, never via `renderTool`).
  2. A **`run_result` SSE event** lifts the chat's `$0` replay record (byte-same to the manual
     Run-eval result) into the shared `runResult`, so the focused Report/Judge tab shows that run.
  3. `ArtifactPane` threads `activeAgent` → `ConfigTab`, so "show its config" loads the **active**
     case's ontology, not the hardcoded `ws0_default`.

## Before → After
| dimension | before (CHATBIND-1) | after (CHATBIND-2) |
|---|---|---|
| who opens the artifact pane | only a human click (card / Run-eval button) | the **conversation** can, via `focus_artifact` |
| chat-driven `$0` run in the pane | rendered only as an inline card | **lifted into the focused Report/Judge tab** (real votes) |
| "show its config" | would show `ws0_default`'s ontology | shows the **active** case's ontology |
| A-SAFE surface | 11 tools, deny-hook gate | **12** tools (+`focus_artifact`, `$0`); deny-hook **byte-identical** |

## Evidence (grounded, not narrated)
- **Live SSE blob:** `docs/research/RUN_chatbind2_alive_2026-06-09.json` (the verbatim event streams).
- **Turn 1** (`ws0_default`, "run a `$0` replay and show me the judge council for this case"):
  `tool_call ToolSearch` *(built-in — **denied by the A-SAFE hook**, no result follows)* →
  `tool_call run_eval` → `tool_result tool-verdict_card {verdict: REJECT, conf 1.00, agreement 1/3}` →
  `run_result {case_id: bench_scribe_v1_inject_condition_1bd0f10dc7b5, pipeline_run_id: a57bd49d-94cd-4397-8c53-f8cbaad3aec2, verdict: reject, votes: [risk_judge PASS 1.0, policy_judge BLOCK, faithfulness_judge BLOCK 1.0]}` →
  `tool_call focus_artifact` → `tool_result tool-open_artifact {tab: judges}` → `done`.
- **Turn 2** ("show its config"): `… → tool_call focus_artifact → tool_result tool-open_artifact {tab: config}`.
- **Frame check (verified during capture):** in `chatbind2_alive_voiced.mp4` at **~76s** the pane is
  focused on **Judge council** with the 3 votes + the inline "↗ Opened the Judge council panel"
  affordance; at **~126s** the pane is focused on **Config** (clinical/1, 23 flags). The offline
  preview was frame-checked identically (judges ~58s, config ~115s) before the voiced render.
- **Reproduce (`$0`):** `curl -s -N -X POST :8787/v1/chat -H 'Content-Type: application/json'
  -d '{"message":"run a $0 replay and show me the judge council for this case","agent":"ws0_default","history":[]}'`
  → assert a `run_result` event + a `tool-open_artifact {tab:"judges"}` part.

## Honest-Δ caveats (the proof includes what did NOT work)
- **The driver's "imported case" 500s on replay.** Every `imported_*` agent (and `s_bs_74_demo`,
  `uap5a_flip_demo`) fails the `$0` replay with `expected str, bytes or os.PathLike object, not
  NoneType` — a **pre-existing backend path-resolution bug, NOT CHATBIND-2** (new seam **S-BS-108**).
  On that first live turn the agent **was honest** rather than fabricate: *"I want to be straight with
  you rather than show a council I didn't actually get back."* That honesty is the moat behaving as
  designed. I switched the demo to `ws0_default` (the canonical runnable scribe case, REJECT + 3 votes).
  **CHATBIND-2's mechanism is proven regardless** — `focus_artifact` fired in BOTH the failed and the
  successful turns; the `run_result` lift correctly did **not** fire on the failed replay (nothing to lift).
- **The model spontaneously tried `ToolSearch` (a built-in).** The PreToolUse deny-hook held — no
  result followed — consistent with the A-SAFE floor (the probe-1 Bash attempt it was built for).
- **A-SAFE intact, live:** the only paid-capable door (the in-DOM cost modal) was never touched; the
  loop ran replay-only; no schema carries a paid knob; the allowlist grew by exactly `focus_artifact`.

## Journey impact
- **Launch-journey phase:** **P2 Verify** → the fully **conversational-first Core** (2026-06-09) —
  every pane (report · judges · config · corpus) is now reachable *by talking*, the capability behind
  the future `frontend` plugin kind (this builds the runtime channel, **not** the plugin registry).
- **De-risk gap:** strengthens **#1 SME-authorable bounded context** — the SME never learns the UI;
  the conversation surfaces the right panel.
- **Unblocks:** a stronger narrated walkthrough (every surface chat-reachable); Plugin Phase-1.

## Video
- **Voiced (deliverable):** `out/zyng_narrate/chatbind2_alive_voiced.mp4` (127.5s, elevenlabs) +
  `.srt`. Drives the **real** app at :5180 through the live A-LIVE (zyng `record_walkthrough`).
- **Offline `$0` preview (selector/timing-validated):** `out/zyng_narrate/chatbind2_alive_preview.mp4`
  (117.0s, silent) + `.srt`.
- Narration: flowing prose, thesis-forward + honest ("I never clicked the panel; the conversation
  drove it… zero paid calls — the agent can never spend").

## References
- Driver `bench-salvage-phaseCHATBIND-2-chat-drives-the-artifact-pane-driver`; session log
  `.devloop/sessions/session-bench-salvage-phaseCHATBIND-2-2026-06-09.json`.
- Builds on **CHATBIND-1** (`PROOF_bench-salvage_CHATBIND-1_2026-06-09.md`). Memory:
  `proof-capsule-convention` · `self-asserting-loop-honesty-moat` · `conversational-first-core-plugin-line`.
