/* JudgeBuilder.jsx — generative-UI input component (tool-judge_builder, PHASE2-C).

   Mints a NEW first-class judge over the active pack's taxonomy snapshot by filling a card in
   the chat. The PROBE (docs/research/PROBE_phase2_arbitrary_judges_2026-06-25.md) confirmed the
   frozen consensus seam already admits N≥2 judges; a new judge needs the authoring bundle —
   {role id, lens codes, optional owned codes (⊆ lens), model binding, role prompt} — written to
   the snapshot blocks (production_judges + lenses + tier1_owners), audited. The SPINE/CONTAINMENT
   invariant (mirror CriterionBuilder): surfacing the card writes NOTHING; the human's "Create reviewer"
   click is the SOLE write via POST /v1/judges (createJudge), THEN onResult() fires. A 422 (owner⊄lens
   / code∉taxonomy / empty lens / role collision / non-core pack) surfaces inline; nothing fires
   onResult on a failed write.

   Two author-time guards, mirrored from the existing surfaces:
   - owner↔emit (JudgeEditor): owned codes MUST be ⊆ lens codes — an owned code outside the lens is
     var-amber + Save-guarded. An empty owned set is allowed (corroborate-only).
   - ⚠ no-logprobs (ModelRegistry/MR-1c): picking a pool model with logprobs:false surfaces the honest
     "confidence dark" hint at pick time.

   The absolute-2 / one-strike HONESTY note (PROBE Q3/Q4) renders inline, verbatim, never overstated:
   a bigger council does NOT raise the corroboration bar (it is a frozen absolute 2). */
import { useEffect, useState } from "react";
import { getOntology, listModels, createJudge } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/ui/card.jsx";
import { Input } from "../components/ui/input.jsx";
import { Label } from "../components/ui/label.jsx";
import { Separator } from "../components/ui/separator.jsx";
import { Icon } from "../icons.jsx";
import { friendlyError } from "./copy.js";
import { registerTool } from "./registry.js";

// A role id is a lower snake token (mirror the server-side guard so the card gates Save locally
// and the human never round-trips a 422 for an obvious format typo).
const ROLE_RE = /^[a-z][a-z0-9_]*$/;

function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

export default function JudgeBuilder({ agent = "ws0_default", role: seedRole, onResult }) {
  const [role, setRole] = useState(seedRole ?? "");
  const [available, setAvailable] = useState([]); // the active pack's codes (the lens source)
  const [lens, setLens] = useState([]); // selected lens codes (codes the judge may raise)
  const [owned, setOwned] = useState([]); // selected owned codes (one-strike owner set) — MUST ⊆ lens
  const [pool, setPool] = useState([]); // the model pool (pick-from-pool, MR-1c)
  const [modelId, setModelId] = useState(""); // chosen pool entry id
  const [rolePrompt, setRolePrompt] = useState("");
  const [rationale, setRationale] = useState("");
  const [returned, setReturned] = useState(false);
  const [persist, setPersist] = useState({ state: "idle", msg: "" }); // idle|saving|saved|error

  // The lens codes come from the active pack's ontology (the same source JudgeEditor's lens reads).
  useEffect(() => {
    let live = true;
    getOntology(agent)
      .then((ont) => { if (live) setAvailable((ont.flags || []).map((f) => f.flag)); })
      .catch(() => {});
    listModels()
      .then((r) => { if (live) setPool(r?.models || []); })
      .catch(() => {});
    return () => { live = false; };
  }, [agent]);

  const toggleLens = (code) =>
    setLens((l) => (l.includes(code) ? l.filter((c) => c !== code) : [...l, code]));
  const toggleOwned = (code) =>
    setOwned((o) => (o.includes(code) ? o.filter((c) => c !== code) : [...o, code]));

  // owner↔emit (JudgeEditor's inline guard): every owned code MUST be in the lens.
  const ownedNotInLens = owned.filter((c) => !lens.includes(c));
  const ownerEmitOk = ownedNotInLens.length === 0;

  const roleValid = ROLE_RE.test(role.trim());
  // admissible to attempt the write: a valid role id, a NON-EMPTY lens, owner↔emit clear.
  const valid = roleValid && lens.length > 0 && ownerEmitOk;

  // the picked pool entry's logprobs flag (for the ⚠ hint at pick time; MR-1c consistency).
  const picked = pool.find((m) => m.id === modelId);
  const pickedLogprobsFalse = picked && !picked.capabilities?.logprobs;

  // Save IS the approval gate: only a successful audited mint fires onResult (the SPINE pattern).
  const apply = async () => {
    setPersist({ state: "saving", msg: "creating…" });
    try {
      const body = {
        role: role.trim(),
        lens_codes: lens,
        owned_codes: owned,
        rationale: rationale.trim(),
        ...(modelId ? { model_id: modelId } : {}),
        ...(rolePrompt.trim() ? { role_prompt: rolePrompt.trim() } : {}),
      };
      const res = await createJudge(body);
      setPersist({ state: "saved", msg: `judge created ✓ (${res.audit_id || "audited"})` });
      setReturned(true);
      onResult?.(res);
    } catch (e) {
      // a 422 admissibility detail is surfaced inline, never swallowed.
      setPersist({ state: "error", msg: friendlyError(e) });
    }
  };

  return (
    <Card className="my-3">
      <CardHeader>
        <span className="text-primary"><Icon name="scale" size={15} /></span>
        <CardTitle>Create reviewer</CardTitle>
        <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">a new reviewer (audited)</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3.5">
        <Field label="Reviewer id">
          <Input value={role} onChange={(e) => setRole(e.target.value)} placeholder="escalation_reviewer" aria-label="reviewer id" aria-invalid={role.length > 0 && !roleValid} />
        </Field>
        {role.length > 0 && !roleValid && <span className="text-[10.5px] text-[color:var(--accent-ink)]">Use lowercase letters and underscores (e.g. escalation_reviewer)</span>}

        <Field label="What this reviewer checks for">
          <div className="flex flex-col gap-1 max-h-44 overflow-y-auto pr-1" data-testid="judge-lens-list">
            {available.length === 0 ? (
              <span className="text-[11px] text-muted-foreground">No checks in this pack yet — create a check first.</span>
            ) : (
              available.map((code) => {
                const inLens = lens.includes(code);
                const isOwned = owned.includes(code);
                const ownedNoLens = isOwned && !inLens;
                return (
                  <div key={code} className="flex items-center gap-2 rounded-[var(--radius-sm)] border border-border bg-background px-2.5 py-1.5">
                    <label className="flex flex-1 items-center gap-2 cursor-pointer">
                      <input type="checkbox" checked={inLens} onChange={() => toggleLens(code)} aria-label={`lens ${code}`} />
                      <span className="font-[family-name:var(--font-mono)] text-[11.5px] text-foreground">{code}</span>
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer" style={ownedNoLens ? { color: "var(--amber)" } : undefined}>
                      <input type="checkbox" checked={isOwned} onChange={() => toggleOwned(code)} aria-label={`own ${code}`} />
                      <span className="text-[10.5px]" style={{ color: ownedNoLens ? "var(--amber)" : "var(--muted)" }}>decisive</span>
                    </label>
                  </div>
                );
              })
            )}
          </div>
        </Field>
        {!ownerEmitOk && (
          <span data-testid="owner-emit-guard" className="text-[10.5px]" style={{ color: "var(--amber)" }}>
            ⚠ {ownedNotInLens.join(", ")} {ownedNotInLens.length > 1 ? "are" : "is"} marked decisive but not in this reviewer's list — a reviewer can only flag a check it watches. Add it to the list, or unmark it.
          </span>
        )}

        <Field label="Model">
          <select
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            aria-label="judge model"
            data-testid="judge-model-select"
            className="flex h-8 w-full rounded-[var(--radius-sm)] border border-input bg-background px-2.5 text-sm text-foreground"
          >
            <option value="">— use the default model —</option>
            {pool.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id} ({m.provider} · {m.model}{m.capabilities?.logprobs ? "" : " · ⚠ no logprobs"})
              </option>
            ))}
          </select>
        </Field>
        {pickedLogprobsFalse && (
          <div data-testid="judge-model-logprobs-hint" className="text-[10.5px]" style={{ color: "var(--amber)" }}>
            ⚠ this model doesn't report a confidence signal — it won't show a confidence number
          </div>
        )}

        <Field label="Instructions (optional)">
          <textarea
            value={rolePrompt}
            onChange={(e) => setRolePrompt(e.target.value)}
            aria-label="role prompt seed"
            data-testid="judge-role-prompt"
            rows={3}
            placeholder="You are the escalation reviewer. Flag an issue only when…"
            className="w-full rounded-[var(--radius-sm)] border border-input bg-background px-2.5 py-1.5 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:border-primary"
          />
        </Field>

        <Field label="Reason (for the audit log)">
          <Input value={rationale} onChange={(e) => setRationale(e.target.value)} placeholder="why this reviewer" aria-label="audit rationale" />
        </Field>

        <Separator />

        {/* The absolute-2 / one-strike HONESTY note (PROBE Q3/Q4) — non-negotiable, verbatim, inline. */}
        <div data-testid="absolute-2-honesty-note" className="rounded-[var(--radius-sm)] border border-border bg-secondary px-3 py-2 text-[11px] leading-relaxed" style={{ color: "var(--muted)" }}>
          Your reviewer votes and corroborates immediately. Adding more reviewers does not raise the bar —
          corroboration is an absolute 2 votes. Solo one-strike authority for a newly-owned code activates on
          the next graded run.
        </div>
      </CardContent>
      <CardFooter>
        <span
          className={
            "font-[family-name:var(--font-mono)] text-[10.5px] " +
            (persist.state === "error" ? "text-[color:var(--accent-ink)]" : "text-muted-foreground")
          }
        >
          {persist.state !== "idle" ? persist.msg : returned ? "reviewer created ✓" : "Saved when you click Create reviewer"}
        </span>
        <Button className="ml-auto" size="sm" onClick={apply} disabled={!valid || persist.state === "saving"}
          title={!valid ? "Give the reviewer a valid id and assign at least one check first" : undefined}>
          {persist.state === "saving" ? "Creating…" : "Create reviewer"}
        </Button>
      </CardFooter>
    </Card>
  );
}

registerTool("tool-judge_builder", JudgeBuilder);
