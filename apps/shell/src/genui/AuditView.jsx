/* AuditView.jsx — generative-UI datapoint component (tool-audit_log, UAP-1 R0).

   The audit-is-the-product surface, minimal: render the config-change stream
   (GET /v1/audit — who/when/what/why for every authoring write) and, on demand, a
   single run's provenance report (GET /v1/runs/{id}/audit — per-judge votes +
   reasoning + verdict). Faithful, not rich — the query/diff views grow in UAP-3.

   All fetches route through bff.js (S-BS-50). */
import { useEffect, useState } from "react";
import { getAudit, getRunAudit } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card.jsx";
import { Input } from "../components/ui/input.jsx";
import { Separator } from "../components/ui/separator.jsx";
import { Icon } from "../icons.jsx";
import { registerTool } from "./registry.js";
import { roleLabel, verdictLabel, friendlyError, gradeTag } from "./copy.js";

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

export default function AuditView({ runId: runIdProp = "" }) {
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [records, setRecords] = useState([]);
  const [runId, setRunId] = useState(runIdProp);
  const [run, setRun] = useState(null);
  const [runErr, setRunErr] = useState(null);

  useEffect(() => {
    let live = true;
    getAudit()
      .then((r) => { if (live) { setRecords(r.records || []); setStatus("ready"); } })
      .catch((e) => { if (live) { setError(friendlyError(e)); setStatus("error"); } });
    return () => { live = false; };
  }, []);

  const loadRun = async () => {
    setRunErr(null); setRun(null);
    try {
      setRun(await getRunAudit(runId));
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
          {status === "loading" && <span className="text-xs text-muted-foreground">Loading audit…</span>}
          {status === "error" && (
            <span className="text-xs text-[color:var(--accent-ink)]">{error}</span>
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
          <span className="text-[11px] font-semibold text-foreground">Run provenance</span>
          <div className="flex items-center gap-2">
            <Input value={runId} onChange={(e) => setRunId(e.target.value)} placeholder="run id"
              aria-label="run id" />
            <Button size="sm" variant="ghost" onClick={loadRun} disabled={!runId}>Load run</Button>
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
              {(run.judges || []).map((j, i) => (
                <div key={i} className="mt-1 text-[10.5px] text-muted-foreground">
                  <span className="text-foreground">{roleLabel(j.judge_role)}</span> {verdictLabel(j.vote)}
                  {j.reasoning ? <> — {j.reasoning}</> : null}
                </div>
              ))}
            </div>
          )}
        </section>
      </CardContent>
    </Card>
  );
}

registerTool("tool-audit_log", AuditView);
