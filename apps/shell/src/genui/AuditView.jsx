/* AuditView.jsx — generative-UI datapoint component (tool-audit_log, UAP-1 R0).

   The audit-is-the-product surface, minimal: render the config-change stream
   (GET /v1/audit — who/when/what/why for every authoring write) and, on demand, a
   single run's provenance report (GET /v1/runs/{id}/audit — per-judge votes +
   reasoning + verdict). Faithful, not rich — the query/diff views grow in UAP-3.

   All fetches route through bff.js (S-BS-50). */
import { useEffect, useState } from "react";
import { getAudit, getRuns, getRunAudit } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card.jsx";
import { Input } from "../components/ui/input.jsx";
import { Separator } from "../components/ui/separator.jsx";
import { Icon } from "../icons.jsx";
import { registerTool } from "./registry.js";
import RunLineage from "./RunLineage.jsx";
import { Spinner } from "../components/Spinner.jsx";
import { roleLabel, verdictLabel, flagLabel, friendlyError, gradeTag } from "./copy.js";

// "{action} {type}:{id}" -> a plain sentence, e.g. "Edited the Faithfulness reviewer".
function auditSentence(rec) {
  const verb = sentenceCase(String(rec?.action || "").replace(/_/g, " ").trim()) || "Changed";
  const type = String(rec?.target?.type || "").toLowerCase();
  const id = rec?.target?.id;
  if (!type && !id) return verb;
  const subject = /judge|reviewer/.test(type) && id ? roleLabel(id) : (id || type);
  return `${verb} the ${subject}`;
}

function sentenceCase(s) {
  const str = String(s || "").trim();
  return str ? str.charAt(0).toUpperCase() + str.slice(1) : str;
}

const verdictTone = (v) => (v === "BLOCK" ? "var(--accent-ink)" : "var(--teal)");

function AuditRow({ rec }) {
  return (
    <div className="rounded-[var(--radius-sm)] border border-border bg-background px-2.5 py-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[11.5px] font-medium text-foreground">
          {auditSentence(rec)}
        </span>
        <span className="font-[family-name:var(--font-mono)] text-[10px] text-muted-foreground">{rec.ts}</span>
      </div>
      <div className="mt-0.5 text-[10.5px] text-muted-foreground">
        {rec.why?.rationale ? <>“{rec.why.rationale}” · </> : null}
        by <span className="text-foreground">{rec.actor?.id}</span>
      </div>
    </div>
  );
}

// RUNTRAIL-11: group the run-history rows by the case they graded (newest-first within
// each group), so the FULL trail of a record reads as one block — "5 runs on case X" —
// instead of a type-the-id loader. Insertion order is preserved (runs arrive newest-first).
function groupByCase(runs) {
  const groups = new Map();
  for (const r of runs) {
    const k = r.case_id || "—";
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(r);
  }
  return [...groups.entries()];
}

function shortTs(ts) {
  const s = String(ts || "");
  const t = s.match(/T(\d{2}:\d{2}:\d{2})/);
  return t ? t[1] : s.slice(0, 19);
}

export default function AuditView({ runId: runIdProp = "", caseId = "" }) {
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [records, setRecords] = useState([]);
  const [runs, setRuns] = useState([]);
  const [runId, setRunId] = useState(runIdProp);
  const [run, setRun] = useState(null);
  const [runErr, setRunErr] = useState(null);
  const [reload, setReload] = useState(0); // B2: a retry bumps this to re-run the loader
  // RUN-TRAIL-CASE-SCOPE: a caseId (threaded from the review_runs card) scopes the trail
  // to the case the conversation is about; "See all runs" is the one-click way out.
  const [caseScope, setCaseScope] = useState(Boolean(caseId));

  useEffect(() => {
    let live = true;
    setStatus("loading"); setError(null);
    getAudit()
      .then((r) => { if (live) { setRecords(r.records || []); setStatus("ready"); } })
      .catch((e) => { if (live) { setError(friendlyError(e)); setStatus("error"); } });
    getRuns(50, caseScope && caseId ? { caseId } : {})
      .then((b) => { if (live) setRuns(b.runs || []); })
      .catch(() => { if (live) setRuns([]); });
    return () => { live = false; };
  }, [reload, caseScope, caseId]);

  const loadRun = async (id) => {
    const target = id || runId;
    if (!target) return;
    setRunId(target); setRunErr(null); setRun(null);
    try {
      setRun(await getRunAudit(target));
    } catch (e) {
      setRunErr(friendlyError(e));
    }
  };

  return (
    <Card className="my-3">
      <CardHeader>
        <span className="text-primary"><Icon name="note" size={15} /></span>
        <CardTitle>Audit trail</CardTitle>
        <span className="text-[10.5px] text-muted-foreground">
          What · When · Why · Who
        </span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <section className="flex flex-col gap-1.5">
          <span className="text-[11px] font-semibold text-foreground">Config changes</span>
          {status === "loading" && (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground"><Spinner size={11} /> Loading audit…</span>
          )}
          {status === "error" && (
            <span className="flex items-center gap-2 text-xs text-[color:var(--accent-ink)]" role="alert">
              {error}
              <Button size="sm" variant="ghost" className="h-5 px-2 text-[11px]" onClick={() => setReload((n) => n + 1)}>Try again</Button>
            </span>
          )}
          {status === "ready" && records.length === 0 && (
            <span className="text-xs text-muted-foreground">No config changes recorded yet.</span>
          )}
          {status === "ready" && records.length > 0 && (
            <div className="flex max-h-56 flex-col gap-1 overflow-y-auto pr-1">
              {records.map((r, i) => <AuditRow key={i} rec={r} />)}
            </div>
          )}
        </section>

        <Separator />

        <section className="flex flex-col gap-1.5">
          <span className="text-[11px] font-semibold text-foreground">Run trail</span>
          {caseScope && caseId && (
            <span className="flex items-center gap-1.5 text-[10.5px] text-muted-foreground" data-testid="trail-scope">
              scoped to <span className="text-foreground">{caseId}</span>
              <Button size="sm" variant="ghost" className="h-5 px-2 text-[10.5px]"
                onClick={() => setCaseScope(false)}>See all runs</Button>
            </span>
          )}
          {runs.length === 0 ? (
            <span className="text-[10.5px] text-muted-foreground">No runs recorded yet.</span>
          ) : (
            <div className="flex max-h-72 flex-col gap-2 overflow-y-auto pr-1" data-testid="run-trail">
              {groupByCase(runs).map(([caseId, rows]) => (
                <div key={caseId} className="flex flex-col gap-0.5" data-testid="trail-case">
                  <div className="flex items-baseline gap-1.5">
                    <span className="text-[10.5px] font-semibold text-foreground">{caseId}</span>
                    <span className="text-[10px] text-muted-foreground">{rows.length} run{rows.length === 1 ? "" : "s"}</span>
                  </div>
                  {rows.map((r) => (
                    <button key={r.run_id} type="button" data-testid="trail-run"
                      onClick={() => loadRun(r.run_id)}
                      className={`flex flex-wrap items-center gap-2 rounded-[var(--radius-sm)] border px-2 py-1 text-left text-[10px] hover:bg-muted ${r.run_id === runId ? "border-primary" : "border-border"}`}>
                      <span className="font-[family-name:var(--font-mono)] text-muted-foreground">{shortTs(r.ts)}</span>
                      <span style={{ color: verdictTone(r.verdict) }}>{verdictLabel(r.verdict)}</span>
                      {/* FLOOR-VIS-1: the grounding floor's outcome rides the row (LAYER0 projection);
                          legacy blobs project null → no chip, nothing fabricated. */}
                      {r.grounded_verdict != null && (
                        <span data-testid="floor-chip"
                          title="The deterministic grounding floor's outcome — the post-floor verdict, and how many judge findings its contracts disproved.">
                          <span className="text-muted-foreground">floor</span>{" "}
                          <span style={{ color: verdictTone(r.grounded_verdict) }}>{verdictLabel(r.grounded_verdict)}</span>
                          {r.floor_suppressed > 0 ? <span className="text-muted-foreground"> · {r.floor_suppressed} suppressed</span> : null}
                        </span>
                      )}
                      {r.grade_path && <span className="text-muted-foreground">{gradeTag(r.grade_path)}</span>}
                      {r.replay_of
                        ? <span className="font-[family-name:var(--font-mono)] text-muted-foreground">↩ replays {(r.replay_of || "").slice(0, 8)}</span>
                        : <span className="text-muted-foreground">authoritative</span>}
                      <span className="ml-auto font-[family-name:var(--font-mono)] text-muted-foreground">{(r.run_id || "").slice(0, 8)}</span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
          <div className="flex items-center gap-2">
            <Input value={runId} onChange={(e) => setRunId(e.target.value)} placeholder="run id"
              aria-label="run id" />
            <Button size="sm" variant="ghost" onClick={() => loadRun()} disabled={!runId}
              title={!runId ? "Pick a run above or paste a run id to load its full report" : undefined}>Load run</Button>
          </div>
          {runErr && (
            <span className="text-[10.5px] text-[color:var(--accent-ink)]">{runErr}</span>
          )}
          {run && (
            <div className="rounded-[var(--radius-sm)] border border-border bg-background px-2.5 py-2 text-[11px]"
              data-testid="run-report">
              <div className="font-medium text-foreground">
                Result: {verdictLabel(run.verdict)} · by {run.actor?.id}
              </div>
              {(run.grade_path || run.replay_of) && (
                <div className="mt-0.5 text-[10px] text-muted-foreground">
                  {run.grade_path ? gradeTag(run.grade_path) : null}
                  {run.replay_of ? <> · ↩ replays {(run.replay_of || "").slice(0, 8)}</> : null}
                </div>
              )}
              {/* FLOOR-VIS-1: the grounding floor's outcome — the verdict flip + every
                  suppression with the deterministic contract that disproved it and its why.
                  Legacy runs carry no grounded block → the section honestly doesn't render. */}
              {run.grounded && (
                <div data-testid="run-grounded" className="mt-1.5 rounded-[var(--radius-sm)] border border-border bg-secondary px-2 py-1.5">
                  <div className="text-[10.5px] font-semibold text-foreground">
                    Grounding floor: {verdictLabel(run.grounded.original_verdict ?? run.verdict)}
                    {" → "}
                    <span style={{ color: verdictTone(run.grounded.verdict) }}>{verdictLabel(run.grounded.verdict)}</span>
                  </div>
                  {(run.grounded.suppressed || []).map((s, i) => (
                    <div key={i} className="mt-0.5 text-[10px] text-muted-foreground">
                      <span className="text-foreground">{flagLabel(s.code)}</span> disproved by{" "}
                      <span className="font-[family-name:var(--font-mono)]">{s.contract}</span>
                      {s.reason ? <> — {s.reason}</> : null}
                      {/* REL-OPS-1 O2: the terminology release that decided it — absent on pre-O2 blobs. */}
                      {s.terminology_edition ? <> · terminology edition: {s.terminology_edition}</> : null}
                    </div>
                  ))}
                  {(run.grounded.suppressed || []).length === 0 && (
                    <div className="mt-0.5 text-[10px] text-muted-foreground">no findings suppressed — the reviewers' verdict stood</div>
                  )}
                </div>
              )}
              {(run.judges || []).map((j, i) => (
                <div key={i} className="mt-1 text-[10.5px] text-muted-foreground">
                  <span className="text-foreground">{roleLabel(j.judge_role)}</span> {verdictLabel(j.vote)}
                  {j.reasoning ? <> — {j.reasoning}</> : null}
                </div>
              ))}
              <RunLineage runId={runId} className="mt-1" />
            </div>
          )}
        </section>
      </CardContent>
    </Card>
  );
}

registerTool("tool-audit_log", AuditView);
