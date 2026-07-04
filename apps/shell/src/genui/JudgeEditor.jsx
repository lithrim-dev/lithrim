/* JudgeEditor.jsx — generative-UI input component (tool-judge_editor, UAP-2 R2).

   Author a judge by ASSIGNING an ontology flag subset to a role (§2A): the assigned
   flags' lens + the role's JudgeQuestions become the judge's refinement questions,
   and the runtime prompt (role_key_questions) is RENDERED from the assignment (the
   prompt↔ontology bridge). The judge may also ATTACH persisted smart-contract
   validators it executes — never generates (execute-only; verification toolbox).

   Demonstrable-by-construction (the load-bearing "aha", user 2026-06-04): as flags
   are toggled, the judge-prompt preview updates LIVE + $0 (no model call) — it shows
   the EXACT rendered role_key_questions the bridge will send (fetched from the same
   render_role_questions via GET /v1/judges/{role}?assigned_flags=…), with a
   before/after vs the seed prompt. The instant assignment→prompt link works with
   zero Azure creds; the live verdict-change is the paid finale (a run, not here).

   Owner↔emit + snapshot are author-time 422 gates (LENS_BY_ROLE authority) surfaced
   inline. All fetches route through bff.js (S-BS-50 — no hardcoded :8787). Built on
   shadcn primitives + the @theme token bridge. */
import { useEffect, useState } from "react";
import { getJudge, listCases, optimizeJudge, putJudge } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/ui/card.jsx";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "../components/ui/dialog.jsx";
import { Input } from "../components/ui/input.jsx";
import { Label } from "../components/ui/label.jsx";
import { Separator } from "../components/ui/separator.jsx";
import { Switch } from "../components/ui/switch.jsx";
import { Spinner } from "../components/Spinner.jsx";
import { Icon } from "../icons.jsx";
import { friendlyError } from "./copy.js";
import { registerTool } from "./registry.js";

const lineCount = (s) => (s ? s.split("\n").length : 0);
const fmt = (x) => (typeof x === "number" ? x.toFixed(2) : "—");

/* The HONEST held-out Δ render (D-G, inline — NOT the calibration_chart reliability
   diagram). Shows baseline→optimized precision/recall/graded on the FIXED test split.
   A win renders the lift; a ≤0 Δ renders EXPLICITLY as a loss (R1 — never hidden,
   never spun; the accept-gate is never loosened to manufacture a win). */
function OptimizeDelta({ result }) {
  const { baseline = {}, optimized = {}, delta = {}, n_train, n_heldout, compile_config = {} } = result;
  const improved = (delta.graded ?? 0) > 0;
  const rows = [
    { k: "graded", label: "Graded (hard-accept)" },
    { k: "precision", label: "Precision" },
    { k: "recall", label: "Recall" },
  ];
  const sign = (d) => (d > 0 ? `+${fmt(d)}` : fmt(d));
  return (
    <div
      data-testid="optimize-delta"
      data-outcome={improved ? "win" : "loss"}
      className="flex flex-col gap-2 rounded-[var(--radius-sm)] border border-border bg-secondary px-3 py-2.5"
    >
      <div className="flex items-baseline justify-between">
        <span className="text-[12px] font-medium text-foreground">Held-out Δ (fixed test split)</span>
        <span className="font-[family-name:var(--font-mono)] text-[10px] text-muted-foreground">
          n_train {n_train ?? "—"} · n_heldout {n_heldout ?? "—"} · {compile_config.n_demos_bootstrapped ?? 0} demos
        </span>
      </div>
      <div className="flex flex-col gap-1">
        {rows.map(({ k, label }) => (
          <div key={k} className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-2 text-[11.5px]">
            <span className="text-muted-foreground">{label}</span>
            <span className="font-[family-name:var(--font-mono)] text-foreground">{fmt(baseline[k])}</span>
            <span className="text-muted-foreground">→ {fmt(optimized[k])}</span>
            <span
              className="font-[family-name:var(--font-mono)] tabular-nums"
              style={{ color: (delta[k] ?? 0) > 0 ? "var(--teal)" : (delta[k] ?? 0) < 0 ? "var(--accent-ink)" : "var(--muted)" }}
            >
              {sign(delta[k] ?? 0)}
            </span>
          </div>
        ))}
      </div>
      {improved ? (
        <span className="text-[11px]" style={{ color: "var(--teal)" }}>
          ✓ optimize improved this judge (+{fmt(delta.graded)} held-out graded). Binding the compiled demos
          back into the production judge is the next step (UAP-4-opt).
        </span>
      ) : (
        <span data-testid="optimize-loss-note" className="text-[11px]" style={{ color: "var(--accent-ink)" }}>
          optimize did not improve this judge — the held-out score did not rise (Δ graded {sign(delta.graded ?? 0)}).
          A trainer, not a demo: the accept-gate is never loosened to manufacture a win.
        </span>
      )}
    </div>
  );
}

export default function JudgeEditor({ role = "risk_judge", agent = "ws0_default", onResult }) {
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [error, setError] = useState(null);
  const [judge, setJudge] = useState(null); // the loaded summary (available_flags, questions, …)
  const [assigned, setAssigned] = useState([]); // assigned flag codes
  const [model, setModel] = useState("");
  // Per-reviewer sampling config (independent-axes model): k completions, temperature, the one
  // injected criterion sentence. Strings for the inputs ("" = use the per-role default).
  const [kSamples, setKSamples] = useState("");
  const [temperature, setTemperature] = useState("");
  const [criterion, setCriterion] = useState("");
  // PROMPT-EDIT-1: the reviewer's base prompt, editable by the SME. `loadedPrompt` is the
  // as-loaded text so a lens-only save doesn't resend an unchanged prompt (no spurious edit).
  const [rolePrompt, setRolePrompt] = useState("");
  const [loadedPrompt, setLoadedPrompt] = useState("");
  const [validators, setValidators] = useState([]); // attached validator refs
  const [actor, setActor] = useState("");
  const [rationale, setRationale] = useState("");
  const [preview, setPreview] = useState({ base: "", rendered: "" });
  const [save, setSave] = useState({ state: "idle", msg: "" }); // idle|saving|saved|error
  const [costOpen, setCostOpen] = useState(false); // the in-DOM cost-confirm modal (S-BS-69)
  const [opt, setOpt] = useState({ state: "idle", result: null, error: null }); // idle|running|done|error
  // optimize-on-subset: the workspace cases (same GET /v1/cases the Cases browser reads) + the
  // SME's chosen subset. Empty selection = whole-workspace (back-compat). A $0 selector, never paid.
  const [cases, setCases] = useState([]);
  const [selectedCaseIds, setSelectedCaseIds] = useState([]);

  useEffect(() => {
    let live = true;
    getJudge(role, { agent })
      .then((j) => {
        if (!live) return;
        setJudge(j);
        setAssigned(j.assigned_flags || []);
        setModel(j.model || "");
        setKSamples(j.k != null ? String(j.k) : "");
        setTemperature(j.temperature != null ? String(j.temperature) : "");
        setCriterion(j.criterion || "");
        setRolePrompt(j.base_prompt || ""); // seed the editable prompt once (initial load only)
        setLoadedPrompt(j.base_prompt || "");
        setValidators(j.validator_refs || []);
        setPreview({ base: j.base_prompt || "", rendered: j.rendered_prompt || "" });
        setStatus("ready");
      })
      .catch((e) => {
        if (!live) return;
        setError(friendlyError(e));
        setStatus("error");
      });
    return () => { live = false; };
  }, [role, agent]);

  // optimize-on-subset: load the workspace's ingested cases ($0) so the SME can scope the
  // optimize to a chosen subset. Same source the Cases browser reads (never drift). A load
  // failure leaves the picker empty (the whole-workspace optimize still works) — never blocks.
  useEffect(() => {
    let live = true;
    listCases()
      .then((r) => { if (live) setCases(r.cases || []); })
      .catch(() => {});
    return () => { live = false; };
  }, []);

  // The live $0 prompt preview: refetch the EXACT rendered role_key_questions for the
  // current assignment whenever it changes (same render_role_questions the bridge uses).
  useEffect(() => {
    if (status !== "ready") return;
    let live = true;
    getJudge(role, { agent, assignedFlags: assigned })
      .then((j) => {
        if (live) setPreview({ base: j.base_prompt || "", rendered: j.rendered_prompt || "" });
      })
      .catch(() => {});
    return () => { live = false; };
  }, [assigned, status, role, agent]);

  if (status === "loading")
    return <Card><CardContent className="flex items-center gap-1.5 text-xs text-muted-foreground"><Spinner size={11} /> Loading reviewer…</CardContent></Card>;
  if (status === "error")
    return (
      <Card>
        <CardContent className="text-xs text-[color:var(--accent-ink)] font-[family-name:var(--font-mono)]">
          We couldn't load this reviewer. Please try again.
        </CardContent>
      </Card>
    );

  const availableFlags = judge.available_flags || [];
  const availableValidators = judge.available_validators || [];
  const questions = judge.questions || [];
  const toggleFlag = (code) =>
    setAssigned((a) => (a.includes(code) ? a.filter((c) => c !== code) : [...a, code]));
  const toggleValidator = (v) =>
    setValidators((vs) => (vs.includes(v) ? vs.filter((x) => x !== v) : [...vs, v]));
  // optimize-on-subset: toggle a case in/out of the chosen subset (order-preserving).
  const toggleCase = (cid) =>
    setSelectedCaseIds((s) => (s.includes(cid) ? s.filter((c) => c !== cid) : [...s, cid]));

  const addedLines = lineCount(preview.rendered) - lineCount(preview.base);

  const persist = async () => {
    setSave({ state: "saving", msg: "saving…" });
    try {
      // PROMPT-EDIT-1: only send role_prompt when the SME actually changed it (last-write-wins on
      // the server; sending it unchanged would log a spurious prompt-edit audit on a lens-only save).
      const body = {
        model, assigned_flags: assigned, validator_refs: validators,
        ...(rolePrompt !== loadedPrompt ? { role_prompt: rolePrompt } : {}),
        // Per-reviewer sampling config — sent only when set; "" leaves the per-role default.
        ...(kSamples !== "" ? { k: Number(kSamples) } : {}),
        ...(temperature !== "" ? { temperature: Number(temperature) } : {}),
        criterion,
      };
      // S-BS-153: pass the active agent so the save ALSO rosters this judge onto its
      // eval_profile.judges (idempotent, audited, server-side) → the rail's Judges step ticks.
      const res = await putJudge(role, body, { actor: actor || undefined, rationale, agent });
      setLoadedPrompt(rolePrompt); // the saved prompt is now the baseline — no resend next save
      setSave({ state: "saved", msg: `saved ✓ as ${res.actor?.id || "dev-default"}` });
      onResult?.(body);
      return res;
    } catch (e) {
      // owner↔emit / snapshot / validator 422 surfaced inline
      setSave({ state: "error", msg: friendlyError(e) });
    }
  };

  // The PAID optimize, gated behind the in-DOM cost modal (S-BS-69 — never
  // window.confirm, which freezes the renderer to CDP). Renders the HONEST held-out
  // Δ (win-or-loss) below; a loss is shown as a loss (R1).
  const runOptimize = async () => {
    setCostOpen(false);
    setOpt({ state: "running", result: null, error: null });
    try {
      // optimize-on-subset: scope to the chosen cases ONLY when a subset is picked — an empty
      // selection sends no case_ids, keeping today's whole-workspace optimize byte-identical.
      const result = await optimizeJudge(role, {
        confirm: true,
        ...(selectedCaseIds.length ? { caseIds: selectedCaseIds } : {}),
      });
      setOpt({ state: "done", result, error: null });
    } catch (e) {
      setOpt({ state: "error", result: null, error: friendlyError(e) });
    }
  };

  return (
    <Card className="my-3">
      <CardHeader>
        <span className="text-primary"><Icon name="scale" size={15} /></span>
        <CardTitle>Judge · {role}</CardTitle>
        <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">
          saved to your checklist
        </span>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="je-model">Model override (optional)</Label>
          <Input id="je-model" value={model} onChange={(e) => setModel(e.target.value)}
            placeholder="leave blank to use the assigned model" />
          {/* VOTE-MODEL-2: show the model this reviewer actually grades on — its Provider-Center
              assignment (or the default) — so a blank override field never reads as "no model". */}
          {judge.effective_model && judge.model_source !== "override" ? (
            <p data-testid="je-effective-model" className="text-[11px] text-muted-foreground">
              Grading on {judge.effective_provider ? `${judge.effective_provider} · ` : ""}
              {judge.effective_model} — set in Providers
            </p>
          ) : judge.model_source === "default" ? (
            <p data-testid="je-effective-model" className="text-[11px] text-muted-foreground">
              Grading on the default model — assign one in Providers
            </p>
          ) : null}
        </div>

        {/* Per-reviewer sampling (independent-axes model): k completions + temperature + the one
            injected criterion sentence. The reviewers are independent axes, never averaged. */}
        <section className="flex flex-col gap-2">
          <Label>Sampling for this reviewer</Label>
          <div className="grid grid-cols-2 gap-2">
            <div className="flex flex-col gap-1">
              <Label htmlFor="je-k" className="text-[10.5px] text-muted-foreground">Samples (k)</Label>
              <Input id="je-k" type="number" min="1" max="9" value={kSamples} data-testid="je-k"
                onChange={(e) => setKSamples(e.target.value)} placeholder="default" />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="je-temp" className="text-[10.5px] text-muted-foreground">Temperature</Label>
              <Input id="je-temp" type="number" min="0" max="2" step="0.1" value={temperature} data-testid="je-temp"
                onChange={(e) => setTemperature(e.target.value)} placeholder="default" />
            </div>
          </div>
          <p className="text-[10.5px] text-muted-foreground">
            More samples stabilize the score by averaging out per-call noise; the spread across the
            k samples is reported as a confidence signal. Temperature applies when k&gt;1 — 1.0
            maximizes the ensembling benefit; k=1 runs deterministically.
          </p>
          <Label htmlFor="je-criterion" className="text-[10.5px] text-muted-foreground">Injected criterion (one sentence)</Label>
          <Input id="je-criterion" value={criterion} data-testid="je-criterion"
            onChange={(e) => setCriterion(e.target.value)}
            placeholder="e.g. Flag any medication dose not present in the transcript." />
        </section>

        <section className="flex flex-col gap-2">
          <Label>Choose what this reviewer checks for</Label>
          <p className="text-[10.5px] text-muted-foreground">
            This reviewer detects and classifies into these codes — findings outside its lens are ignored.
          </p>
          <div className="flex max-h-56 flex-col gap-1 overflow-y-auto pr-1">
            {availableFlags.map((f) => (
              <div key={f.flag} className="flex items-center gap-2 rounded-[var(--radius-sm)] border border-border bg-background px-2.5 py-2">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-[family-name:var(--font-mono)] text-[12px] font-medium text-foreground">
                    {f.flag} <span className="text-[10px] text-muted-foreground">{f.tier || ""}</span>
                  </div>
                  <div className="truncate text-[10.5px] text-muted-foreground">{f.when_to_use || "—"}</div>
                </div>
                <Switch
                  checked={assigned.includes(f.flag)}
                  onCheckedChange={() => toggleFlag(f.flag)}
                  aria-label={`assign ${f.flag}`}
                />
              </div>
            ))}
          </div>
        </section>

        <section className="flex flex-col gap-2">
          <Label>Attach fact-checks</Label>
          <div className="flex flex-wrap gap-1.5">
            {availableValidators.map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => toggleValidator(v)}
                aria-pressed={validators.includes(v)}
                aria-label={`validator ${v}`}
                className={
                  "rounded-[var(--radius-sm)] border px-2 py-1 font-[family-name:var(--font-mono)] text-[11px] " +
                  (validators.includes(v)
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border bg-background text-muted-foreground")
                }
              >
                {v}
              </button>
            ))}
          </div>
        </section>

        <Separator />

        <section className="flex flex-col gap-2">
          <Label>Follow-up questions (from your checklist)</Label>
          {questions.length ? (
            <ol className="flex flex-col gap-0.5 pl-4 text-[11.5px] text-muted-foreground">
              {questions.map((q) => (
                <li key={q.ordinal} className="list-decimal">{q.text}</li>
              ))}
            </ol>
          ) : (
            <span className="text-[11px] text-muted-foreground">No authored questions for this role yet.</span>
          )}
        </section>

        {/* PROMPT-EDIT-1: the SME edits what this reviewer looks for — saved with the reviewer, no
            code change. Assigned checks are appended automatically (shown in the rendered preview). */}
        <section className="flex flex-col gap-1.5">
          <Label htmlFor="je-role-prompt">Reviewer prompt — edit what this reviewer looks for</Label>
          <textarea
            id="je-role-prompt"
            data-testid="je-role-prompt"
            value={rolePrompt}
            onChange={(e) => setRolePrompt(e.target.value)}
            rows={8}
            spellCheck={false}
            aria-label="reviewer prompt"
            className="resize-y rounded-[var(--radius-sm)] border border-border bg-background px-3 py-2 font-[family-name:var(--font-mono)] text-[11px] leading-snug text-foreground"
          />
          <span className="text-[10.5px] text-muted-foreground">Saved with this reviewer · assigned checks are appended automatically below</span>
        </section>

        <section className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between">
            <Label>Rendered prompt preview (prompt + assigned checks this reviewer will ask)</Label>
            <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">
              {assigned.length
                ? `+${addedLines} lines vs seed · ${assigned.length} flag${assigned.length > 1 ? "s" : ""} · $0`
                : "seed prompt (no assignment) · $0"}
            </span>
          </div>
          <pre className="max-h-48 overflow-auto rounded-[var(--radius-sm)] border border-border bg-secondary px-3 py-2 font-[family-name:var(--font-mono)] text-[10.5px] leading-snug whitespace-pre-wrap text-foreground">
            {preview.rendered || preview.base}
          </pre>
        </section>

        <Separator />

        <section className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between">
            <Label>Optimize (calibration trainer)</Label>
            <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">
              Improve this reviewer · paid
            </span>
          </div>
          <p className="text-[10.5px] text-muted-foreground">
            Compile few-shot demos from the by-construction calibration split, then measure the
            honest held-out Δ on the fixed test split. Did the edit move the number? — win or loss,
            shown straight.
          </p>
          {/* optimize-on-subset: scope the calibration to a CHOSEN case set. No selection =
              the whole workspace (today's behaviour). A $0 selector — the paid confirm is below. */}
          {cases.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between">
                <Label className="text-[10.5px] text-muted-foreground">
                  Scope to cases (optional)
                </Label>
                <span data-testid="optimize-subset-count" className="font-[family-name:var(--font-mono)] text-[10px] text-muted-foreground">
                  {selectedCaseIds.length
                    ? `${selectedCaseIds.length} chosen`
                    : `all ${cases.length}`}
                </span>
              </div>
              <div className="flex max-h-40 flex-col gap-1 overflow-y-auto pr-1">
                {cases.map((c) => (
                  <label
                    key={c.case_id}
                    className="flex items-center gap-2 rounded-[var(--radius-sm)] border border-border bg-background px-2.5 py-1.5"
                  >
                    <input
                      type="checkbox"
                      data-testid={`optimize-case-${c.case_id}`}
                      checked={selectedCaseIds.includes(c.case_id)}
                      onChange={() => toggleCase(c.case_id)}
                    />
                    <span className="min-w-0 flex-1 truncate font-[family-name:var(--font-mono)] text-[11px] text-foreground">
                      {c.case_id}
                    </span>
                    {c.labeled ? (
                      <span className="text-[9.5px] text-muted-foreground">labeled</span>
                    ) : (
                      <span className="text-[9.5px] text-muted-foreground">no gold</span>
                    )}
                  </label>
                ))}
              </div>
              <p className="text-[10px] text-muted-foreground">
                Leave all unchecked to calibrate on the whole workspace. Only labeled cases feed
                the split; a subset too small to split is refused, never silently skipped.
              </p>
            </div>
          )}
          <div className="flex items-center gap-3">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setCostOpen(true)}
              disabled={opt.state === "running"}
            >
              {opt.state === "running" ? "Optimizing…" : "Optimize"}
            </Button>
            {opt.state === "running" && (
              <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">
                running the trainset bootstrap + 2 held-out evals…
              </span>
            )}
          </div>
          {opt.state === "error" && (
            <div className="font-[family-name:var(--font-mono)] text-[11px] text-[color:var(--accent-ink)]">
              Couldn't improve the reviewer — please try again.
            </div>
          )}
          {opt.state === "done" && opt.result && <OptimizeDelta result={opt.result} />}
        </section>

        <Separator />
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="je-actor">Your name</Label>
            <Input id="je-actor" value={actor} onChange={(e) => setActor(e.target.value)}
              placeholder="you@example.com" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="je-why">Reason for this change</Label>
            <Input id="je-why" value={rationale} onChange={(e) => setRationale(e.target.value)}
              placeholder="why this change" />
          </div>
        </div>
      </CardContent>
      <CardFooter>
        <span
          className={
            "font-[family-name:var(--font-mono)] text-[10.5px] " +
            (save.state === "error" ? "text-[color:var(--accent-ink)]" : "text-muted-foreground")
          }
        >
          {save.state !== "idle" ? save.msg : "Save reviewer"}
        </span>
        <Button className="ml-auto" size="sm" onClick={persist} disabled={save.state === "saving"}>
          {save.state === "saving" ? "Saving…" : "Save judge"}
        </Button>
      </CardFooter>

      {/* In-DOM cost-confirm modal (S-BS-69 — driveable by automation, unlike
          window.confirm which freezes the renderer to CDP). */}
      <Dialog open={costOpen} onOpenChange={setCostOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Paid optimize run</DialogTitle>
            <DialogDescription>
              Optimizing {role} makes real Azure calls — a bootstrap compile over the trainset plus
              two held-out evals × the judge (~$0.26). The held-out Δ is reported honestly, win or
              loss. Continue?
            </DialogDescription>
          </DialogHeader>
          <div className="mt-2 flex justify-end gap-2">
            <Button size="sm" variant="outline" onClick={() => setCostOpen(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={runOptimize} data-testid="optimize-confirm">
              Run optimize (paid)
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

registerTool("tool-judge_editor", JudgeEditor);
