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
import { getJudge, putJudge } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/ui/card.jsx";
import { Input } from "../components/ui/input.jsx";
import { Label } from "../components/ui/label.jsx";
import { Separator } from "../components/ui/separator.jsx";
import { Switch } from "../components/ui/switch.jsx";
import { Icon } from "../icons.jsx";
import { registerTool } from "./registry.js";

const lineCount = (s) => (s ? s.split("\n").length : 0);

export default function JudgeEditor({ role = "risk_judge", agent = "ws0_default", onResult }) {
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [error, setError] = useState(null);
  const [judge, setJudge] = useState(null); // the loaded summary (available_flags, questions, …)
  const [assigned, setAssigned] = useState([]); // assigned flag codes
  const [model, setModel] = useState("");
  const [validators, setValidators] = useState([]); // attached validator refs
  const [actor, setActor] = useState("");
  const [rationale, setRationale] = useState("");
  const [preview, setPreview] = useState({ base: "", rendered: "" });
  const [save, setSave] = useState({ state: "idle", msg: "" }); // idle|saving|saved|error

  useEffect(() => {
    let live = true;
    getJudge(role, { agent })
      .then((j) => {
        if (!live) return;
        setJudge(j);
        setAssigned(j.assigned_flags || []);
        setModel(j.model || "");
        setValidators(j.validator_refs || []);
        setPreview({ base: j.base_prompt || "", rendered: j.rendered_prompt || "" });
        setStatus("ready");
      })
      .catch((e) => {
        if (!live) return;
        setError(String(e.message || e));
        setStatus("error");
      });
    return () => { live = false; };
  }, [role, agent]);

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
    return <Card><CardContent className="text-xs text-muted-foreground">Loading judge…</CardContent></Card>;
  if (status === "error")
    return (
      <Card>
        <CardContent className="text-xs text-[color:var(--accent-ink)] font-[family-name:var(--font-mono)]">
          Could not read judge: {error}
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

  const addedLines = lineCount(preview.rendered) - lineCount(preview.base);

  const persist = async () => {
    setSave({ state: "saving", msg: "saving…" });
    try {
      const body = { model, assigned_flags: assigned, validator_refs: validators };
      const res = await putJudge(role, body, { actor: actor || undefined, rationale });
      setSave({ state: "saved", msg: `saved ✓ as ${res.actor?.id || "dev-default"}` });
      onResult?.(body);
      return res;
    } catch (e) {
      // owner↔emit / snapshot / validator 422 surfaced inline
      setSave({ state: "error", msg: String(e.message || e) });
    }
  };

  return (
    <Card className="my-3">
      <CardHeader>
        <span className="text-primary"><Icon name="scale" size={15} /></span>
        <CardTitle>Judge · {role}</CardTitle>
        <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">
          ontology-assignment · attributed write
        </span>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="je-model">Model deployment</Label>
          <Input id="je-model" value={model} onChange={(e) => setModel(e.target.value)}
            placeholder="AZURE_OPENAI_DEPLOYMENT_COUNCIL" />
        </div>

        <section className="flex flex-col gap-2">
          <Label>Assign lens (owned + emitted codes)</Label>
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
          <Label>Attach validators (execute-only)</Label>
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
          <Label>Refinement questions (derived from the ontology)</Label>
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

        <section className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between">
            <Label>Judge prompt preview (the exact role_key_questions)</Label>
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
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="je-actor">Your handle (audit who)</Label>
            <Input id="je-actor" value={actor} onChange={(e) => setActor(e.target.value)}
              placeholder="sme@acme-health" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="je-why">Rationale (audit why)</Label>
            <Input id="je-why" value={rationale} onChange={(e) => setRationale(e.target.value)}
              placeholder="why this lens" />
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
          {save.state !== "idle" ? save.msg : "PUT /v1/judges · owner↔emit + snapshot gated (not the seed)"}
        </span>
        <Button className="ml-auto" size="sm" onClick={persist} disabled={save.state === "saving"}>
          {save.state === "saving" ? "Saving…" : "Save judge"}
        </Button>
      </CardFooter>
    </Card>
  );
}

registerTool("tool-judge_editor", JudgeEditor);
