# Pitch demo runbook — "hand them the laptop"

**The pitch shape:** a prospect drives the conversation ("talk to the system about this case, it
walks you through"); then you come in and reveal the flip ("if we add this flag/criterion, here's
what changes"). Part A is theirs; **the flip (Part B) stays in your hands.**

**Honesty bar (the whole pitch rests on this):** the live council agrees with the physician **8/10**
on Dr Sharif's suite — say 8/10, never 10/10. The 2 misses (case 02 omission, **case 10 dissent
erasure**) ARE the wedge: that's exactly what authoring a grounding floor fixes. The flip is real and
PAID-real; never manufacture it.

---

## T-30 — before the room

> Run the stack from a **fresh terminal that has never run a Claude Code session** (this is the #1
> demo killer — see Guardrails). Then:

1. **Start + health.**
   ```
   make up        # BFF :8787 (watch) + UI :5180 (HMR)
   make status    # ports + health — wait until BFF /health is UP
   make health    # BFF up? + a $0 replay grade (proves grading works, no spend)
   ```
   `make up` auto-discovers the sibling `../lithrim-pack-healthcare` pack (S-BS-140). If `make health`
   is green you're live.

2. **Confirm chat works** (BYO-Claude subscription). Open `http://localhost:5180`, type "hello" in the
   chat. If it replies → auth is good. If you see **401 / "Invalid authentication credentials"** → see
   Guardrails → "Chat auth."

3. **Pre-stage the safety net** (do this even if you plan the live-authored flip). On a **dedicated
   tier:core workspace built for case 10** — the narrative pack used purely as the self-authorable
   *vehicle* (this is the honest boundary: healthcare is tier:pro and not self-authorable; case 10 is
   clinical content graded against a tier:core workspace). Create this workspace fresh for the demo
   (do NOT reuse `storyworld_` — that's a separate, non-clinical narrative workspace). Give it an agent,
   then:
   - Mint the criterion `DISSENT_ERASURE` (TIER_1 / `policy_judge`) — chat: *"Add a gradeable criterion
     DISSENT_ERASURE, tier 1, owned by policy_judge"* → Save on the card → "criterion minted ✓".
   - Author the `value_presence` floor on it (chat: *"Add a grounding floor that blocks when the
     patient's refusal is recorded in the transcript but erased from the SOAP"*). The card now opens on
     **value_presence** (S-BS-143 fix). Save.
   - Load **case 10**, run the grade once to confirm: **council PASS → floor BLOCK → reject**. This is
     your guaranteed money-shot if the live-authored path wobbles.

4. **Rehearse the live-authored flip once** on the actual machine. The S-BS-143 fix makes the ASSIST
   pick `value_presence` correctly, but verify it end-to-end before the room — the fix is code-correct,
   the rehearsal is the proof.

---

## In the room

### Part A — prospect drives (theirs)
- Hand them the laptop on **case 10 already loaded**. Prompt them: *"Ask it what this case is about,
  and whether the AI's note is trustworthy."*
- It walks them through: the SOAP, the council verdict + per-judge votes, the dissent. **All inline in
  the chat** — they never touch the side pane.
- Let them poke. The chat is read-mostly here; nothing they type spends money on its own (paid runs
  are confirm-gated — see Guardrails).

### Part B — you reveal the flip (yours)
- Take the laptop back. "Notice the council **approved** this — it missed that the patient refused the
  vaccine and the note erased it. Watch what happens when we add a rule for that."
- **Either:** author the floor live by talking (the headline — now trustworthy), **or** flip to your
  pre-staged workspace and re-grade.
- Result: **council PASS → value_presence floor BLOCK → verdict flips to reject, DISSENT_ERASURE
  injected.** That's the whole thesis in one screen: a clinician taught the system to catch what a
  generic council missed, by talking.

---

## Guardrails

- **Chat auth (the #1 killer).** The BFF must run with a clean env. If you got a 401, restart the BFF
  from a terminal that never ran a Claude session, or strip the inherited vars:
  ```
  env -u ANTHROPIC_BASE_URL -u CLAUDE_CODE_ENTRYPOINT -u CLAUDECODE -u CLAUDE_CODE_SESSION_ID \
      ANTHROPIC_API_KEY="" bash scripts/dev/devstack.sh start bff
  ```
  (Full var list in the `dev-bff-runtime-config-plane` memory.) Needs a current `claude login`.
- **Paid runs.** A live council run ("Run live" / `in_process`) is **real Azure spend** and is
  **confirm-gated** — it won't fire without a click. Don't let a prospect trigger one by surprise; if
  the room asks for a fresh live run, you click the confirm. `make probe` also spends (tiny) — don't
  run it mid-demo. The `make health` replay is **$0**.
- **Keep the pane closed.** The product is conversational-first — everything actionable is inline. If
  you find yourself driving pane tabs to advance, you've left the demo's spine.
- **Workspace.** The governed flip lives in a **narrative (tier:core sample) pack** — that's the honest
  boundary (healthcare is tier:pro, deliberately not self-authorable). Don't try to mint into
  healthcare on stage; the writer refuses it (correctly).

## If it breaks
- **Chat dead / 401** → restart BFF with the stripped-env recipe above; re-test "hello".
- **Stale server / weird state** → `make down`, confirm `/health` is DOWN, `make up`. (A `--reload`
  worker can outlive a plain kill — `lsof -ti tcp:8787 | xargs kill -9` if `make down` doesn't clear
  the port.)
- **Live-authored flip won't fire** → fall back to the **pre-staged workspace** and re-grade. Same
  money-shot, deterministic.
