/* CriterionJuteBuilder.jsx — generative-UI input component (tool-criterion_jute_builder,
   CRITERION-JUTE-1d). The inline card that ties the CRITERION-JUTE stack together: an SME picks a
   tool+call, a plain-English criterion seeds generation of the per-case arguments_jute (1b), the
   bidirectional subsumption corpus gate runs (1c), the GateReport renders inline, and the mcp_call +
   arguments_jute contract PINS on pass (1a).

   Two-step flow: "Generate + gate" -> generateCriterionJute({commit:false}) is a $0 PREVIEW (the
   argshape + gate report, writes NOTHING); "Pin" -> generateCriterionJute({commit:true}) writes the
   contract through the SAME audited put path, DISABLED until gate_report.passed. onResult fires ONLY
   on a successful pin (the human's Pin is the write). The mirror is ContractBuilder (a $0 surface;
   the human's Save writes). */
import { useEffect, useState } from "react";
import { listTools, generateCriterionJute } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/ui/card.jsx";
import { Input } from "../components/ui/input.jsx";
import { Label } from "../components/ui/label.jsx";
import { Separator } from "../components/ui/separator.jsx";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select.jsx";
import { Icon } from "../icons.jsx";
import { friendlyError } from "./copy.js";
import { registerTool } from "./registry.js";

function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

// The registry spreads part.output = {agent, flag_code, tool, call, criterion} as props (the
// author_contract handler's seed for a tool-grounded flag). Defaults keep the direct-render /
// offline (vitest) paths working with no server.
export default function CriterionJuteBuilder({ agent = "ws0_default", flag_code = "", tool: seedTool = "", call: seedCall = "", criterion: seedCriterion = "", onResult }) {
  const [tools, setTools] = useState(seedTool ? [seedTool] : []);
  const [tool, setTool] = useState(seedTool);
  const [call, setCall] = useState(seedCall);
  const [criterion, setCriterion] = useState(seedCriterion);
  // idle -> generating -> gated -> pinning -> pinned | error
  const [state, setState] = useState("idle");
  const [msg, setMsg] = useState("");
  const [preview, setPreview] = useState(null); // {arguments_jute, arguments_jute_sha256, gate_report}

  // list the workspace's tools on mount (declared ∪ authored); keep the seeded tool selectable.
  useEffect(() => {
    let live = true;
    listTools()
      .then((r) => {
        if (!live) return;
        const ids = [...(r?.declared || []), ...(r?.authored || [])].map((t) => t?.id).filter(Boolean);
        const merged = seedTool && !ids.includes(seedTool) ? [seedTool, ...ids] : ids;
        if (merged.length) setTools(merged);
      })
      .catch(() => {}); // offline / first paint -> keep the seed-only list
    return () => { live = false; };
  }, []);

  const gate = preview?.gate_report;
  const passed = !!gate?.passed;
  const canGenerate = tool && call && state !== "generating" && state !== "pinning";

  const runPreview = async () => {
    setState("generating");
    setMsg("generating + gating…");
    try {
      const res = await generateCriterionJute({ flag_code, tool, call, criterion, commit: false, agent });
      setPreview(res);
      setState("gated");
      setMsg(res?.gate_report?.passed ? "gate passed ✓" : "gate failed — see the report");
    } catch (e) {
      setState("error");
      setMsg(friendlyError(e));
    }
  };

  const pin = async () => {
    setState("pinning");
    setMsg("pinning…");
    try {
      const res = await generateCriterionJute({ flag_code, tool, call, criterion, commit: true, agent });
      setState("pinned");
      setMsg("contract pinned ✓");
      onResult?.(res?.contract || { flag_code, tool, call });
    } catch (e) {
      setState("error");
      setMsg(friendlyError(e));
    }
  };

  return (
    <Card className="my-3">
      <CardHeader>
        <span className="text-primary"><Icon name="shield" size={15} /></span>
        <CardTitle>Tool-grounded criterion</CardTitle>
        <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">criterion → generate → gate → pin</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3.5">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Tool">
            <Select value={tool} onValueChange={setTool}>
              <SelectTrigger aria-label="tool"><SelectValue placeholder="pick a tool" /></SelectTrigger>
              <SelectContent>
                {tools.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Call">
            <Input value={call} onChange={(e) => setCall(e.target.value)} placeholder="e.g. subsumed_by" aria-label="call" />
          </Field>
        </div>
        <Field label="Criterion — plain English">
          <textarea
            value={criterion}
            onChange={(e) => setCriterion(e.target.value)}
            rows={3}
            spellCheck={false}
            aria-label="criterion"
            placeholder="The note diagnosis must not be more specific than the record supports."
            className="resize-y rounded-[var(--radius-sm)] border border-border bg-background px-3 py-2 text-[12px] leading-snug text-foreground"
          />
        </Field>
        <div>
          <Button variant="secondary" size="sm" onClick={runPreview} disabled={!canGenerate}>
            {state === "generating" ? "Generating…" : "Generate + gate"}
          </Button>
        </div>
        {gate && (
          <>
            <Separator />
            <div className="flex flex-col gap-2 text-[12px]">
              <div className="flex items-center gap-3">
                <span className={"rounded-[var(--radius-sm)] px-2 py-0.5 " + (passed ? "bg-secondary text-[color:var(--teal)]" : "bg-accent text-[color:var(--accent-ink)]")}>
                  {passed ? "gate passed" : "gate failed"}
                </span>
                <span className="text-muted-foreground">negatives cleared {gate.negatives_cleared}/{gate.negatives_total}</span>
                <span className="text-muted-foreground">positives standing {gate.positives_standing}/{gate.positives_total}</span>
                <span className="text-muted-foreground">span-bind {gate.span_bind_ok}/{gate.span_bind_cases}</span>
              </div>
              {gate.failures?.length > 0 && (
                <div data-testid="gate-failures" className="rounded-[var(--radius-sm)] border border-border bg-secondary px-3 py-2 font-[family-name:var(--font-mono)] text-[11px] text-[color:var(--accent-ink)]">
                  failing cases: {gate.failures.join(", ")}
                </div>
              )}
            </div>
          </>
        )}
      </CardContent>
      <CardFooter>
        <span
          className={
            "font-[family-name:var(--font-mono)] text-[10.5px] " +
            (state === "error" ? "text-[color:var(--accent-ink)]" : "text-muted-foreground")
          }
        >
          {state !== "idle" ? msg : "author a tool-grounded criterion"}
        </span>
        <Button className="ml-auto" size="sm" onClick={pin} disabled={!passed || state === "pinning" || state === "pinned"}>
          {state === "pinning" ? "Pinning…" : "Pin contract"}
        </Button>
      </CardFooter>
    </Card>
  );
}

registerTool("tool-criterion_jute_builder", CriterionJuteBuilder);
