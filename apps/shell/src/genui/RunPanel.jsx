/* RunPanel.jsx — generative-UI processing surface (tool-run_panel, UAP-3 R4).

   The Stage-3 "processing" surface: trigger a graded run, show its composite verdict +
   the realized per-judge council votes, and list the run-history (each row addressable
   for its audit). This is where an authored judge's verdict-change becomes visible.

   Cost posture (plan-review Decision 3): replay (live=false) is the $0 default; live
   and in_process are PAID and gated behind an explicit confirm before any call. The
   in_process path is the one an authored judge re-votes on (S-BS-63).

   All fetches route through bff.js (S-BS-50 — no hardcoded :8787). Follows the LOCKED
   flat-spread prop convention (registry.js): props are spread from part.output; this
   component reads only `agent`. */
import { useEffect, useState } from "react";
import { getRuns, runEval } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/ui/card.jsx";
import { Separator } from "../components/ui/separator.jsx";
import { CostModal } from "../components/CostModal.jsx";
import { Icon } from "../icons.jsx";
import { registerTool } from "./registry.js";
import RunLineage from "./RunLineage.jsx";
import { verdictLabel, roleLabel, gradeTag, friendlyError } from "./copy.js";

const MODES = [
  { key: "replay", label: "Replay", cost: "$0", paid: false },
  { key: "live", label: "Live run", cost: "paid", paid: true },
  { key: "in_process", label: "In-process trio", cost: "paid", paid: true },
];

const COST_BODY =
  "This is a paid run (real model calls, about $0.10–0.20). This makes real model calls you'll be billed for. " +
  "A saved replay is the free default. Continue?";

const voteTone = (vote) =>
  vote === "BLOCK" ? "var(--accent-ink)" : vote === "WARN" ? "var(--amber, #b45309)" : "var(--teal)";

const verdictTone = (v) => (v === "BLOCK" ? "var(--accent-ink)" : "var(--teal)");

// RUNTRAIL-8: one run-history row + its lineage. Surfaces grade_path (cost tag) +
// replay_of (the baseline this run replays); the History expander + $0 Rehydrate live in the
// shared RunLineage component (same source as AuditView).
function HistoryRow({ r }) {
  return (
    <div className="flex flex-col gap-1" data-testid="history-row">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">
          {(r.run_id || "").slice(0, 8)}
        </span>
        <span style={{ color: verdictTone(r.verdict) }}>{verdictLabel(r.verdict)}</span>
        <span className="text-muted-foreground">{r.agent}</span>
        {r.grade_path && (
          <span className="text-[10px] text-muted-foreground">{gradeTag(r.grade_path)}</span>
        )}
        {r.replay_of && (
          <span className="font-[family-name:var(--font-mono)] text-[10px] text-muted-foreground">
            ↩ replays {(r.replay_of || "").slice(0, 8)}
          </span>
        )}
      </div>
      <RunLineage runId={r.run_id} />
    </div>
  );
}

export default function RunPanel({ agent = "ws0_default", onRan }) {
  const [mode, setMode] = useState("replay");
  const [runStatus, setRunStatus] = useState("idle"); // idle | running | done | error
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  // EVAL-FLOW (W2a / S-BS-69): the PAID gate is an in-DOM modal, never window.confirm (a native
  // confirm() freezes the renderer to CDP — memory browser-mcp-confirm-blocks-renderer — so a paid
  // run can't be driven in the A-LIVE re-drive). `paid.open` shows the modal; only its confirm runs.
  const [paid, setPaid] = useState({ open: false, busy: false });

  const loadHistory = () =>
    getRuns()
      .then((b) => setHistory(b.runs || []))
      .catch(() => setHistory([]));

  useEffect(() => {
    let live = true;
    getRuns()
      .then((b) => live && setHistory(b.runs || []))
      .catch(() => live && setHistory([]));
    return () => { live = false; };
  }, []);

  // Fire the actual run. Replay ($0) calls directly; a paid mode reaches here only AFTER the
  // in-DOM cost modal's confirm (the human authorizes the spend) — there is no window.confirm.
  const doRun = async () => {
    setRunStatus("running");
    setError(null);
    try {
      const rec = await runEval({ agent, live: mode === "live", in_process: mode === "in_process" });
      setResult(rec);
      setRunStatus("done");
      await loadHistory();
      // EVAL-FLOW (W3): signal up so App.refreshJourney re-derives — a run for this agent ticks Run.
      onRan?.(rec);
    } catch (e) {
      setError(friendlyError(e)); // calm, leak-free reason (never a raw HTTP/path/stack)
      setRunStatus("error");
    }
  };

  const runNow = () => {
    const m = MODES.find((x) => x.key === mode);
    // Cost gate: a paid mode opens the in-DOM modal (no call yet); replay runs straight away.
    if (m.paid) { setPaid({ open: true, busy: false }); return; }
    doRun();
  };

  const confirmPaid = async () => {
    setPaid((p) => ({ ...p, busy: true }));
    try {
      await doRun();
    } finally {
      setPaid({ open: false, busy: false });
    }
  };

  const comp = result?.composite;
  const votes = result?.council?.votes || [];

  return (
    <Card className="my-3">
      <CardHeader>
        <span className="text-primary"><Icon name="bolt" size={15} /></span>
        <CardTitle>Run evaluation</CardTitle>
        <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">
          processing · {agent}
        </span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Run mode">
          {MODES.map((m) => (
            <Button
              key={m.key}
              size="sm"
              variant={mode === m.key ? "default" : "outline"}
              onClick={() => setMode(m.key)}
            >
              {m.label} <span className="ml-1.5 opacity-60">{m.cost}</span>
            </Button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <Button size="sm" onClick={runNow} disabled={runStatus === "running"}>
            {runStatus === "running" ? "Running…" : "Run now"}
          </Button>
          {/* SWEEP (RIGOR-1 / Q1 — NEW-G3): a $0 read that plots this reviewer's self-consistency
              across K samples INLINE via the lithrim:show-sweep window bridge (the same idiom as
              the ⌘K trigger). Adds NO agent tool; the shell emits the tool-sweep_card. */}
          <Button size="sm" variant="outline" data-testid="sweep-trigger"
            onClick={() => { try { window.dispatchEvent(new CustomEvent("lithrim:show-sweep")); } catch {} }}>
            Reliability sweep <span className="ml-1.5 opacity-60">$0</span>
          </Button>
          {result?.pipeline_run_id && (
            <span className="font-[family-name:var(--font-mono)] text-[10.5px] text-muted-foreground">
              run {result.pipeline_run_id.slice(0, 8)} · {result.grade_path}
            </span>
          )}
        </div>

        {runStatus === "error" && (
          <div className="flex items-center gap-2 text-xs text-[color:var(--accent-ink)]" role="alert">
            <span>{error || "We couldn't finish that run."}</span>
            <Button size="sm" variant="ghost" className="h-5 px-2 text-[11px]" onClick={runNow}>Try again</Button>
          </div>
        )}

        {comp && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 text-sm">
              <strong>Result</strong>
              <span style={{ color: comp.verdict === "reject" ? "var(--accent-ink)" : "var(--teal)" }}>
                {verdictLabel(comp.verdict)}
              </span>
              <span className="text-muted-foreground text-xs">
                (stage {verdictLabel(comp.stage_verdict)}, score {comp.score})
              </span>
            </div>
            <div className="flex flex-col gap-1">
              {votes.map((v, i) => (
                <div key={i} className="flex items-center gap-2 text-xs" data-testid="council-vote">
                  <span style={{ color: voteTone(v.vote), fontWeight: 600 }}>{verdictLabel(v.vote)}</span>
                  <span className="text-foreground">{roleLabel(v.judge_role)}</span>
                  <span className="text-muted-foreground">
                    {v.confidence == null ? "how sure —" : `how sure ${v.confidence}`}
                    {v.findings?.length ? ` · ${v.findings.join(", ")}` : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <Separator />
        <div className="flex flex-col gap-1">
          <div className="text-xs font-medium text-muted-foreground">
            Run history {history.length ? `(${history.length})` : "(none yet)"}
          </div>
          {history.map((r) => (
            <HistoryRow key={r.run_id} r={r} />
          ))}
        </div>
      </CardContent>
      <CardFooter>
        <span className="text-[10.5px] text-muted-foreground">
          A saved replay is free; a live run is paid
        </span>
      </CardFooter>
      <CostModal
        open={paid.open}
        busy={paid.busy}
        title="Run a paid evaluation?"
        body={COST_BODY}
        confirmLabel="Run (paid)"
        onConfirm={confirmPaid}
        onCancel={() => setPaid({ open: false, busy: false })}
      />
    </Card>
  );
}

registerTool("tool-run_panel", RunPanel);
