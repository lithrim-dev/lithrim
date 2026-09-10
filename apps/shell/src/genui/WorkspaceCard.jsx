/* WorkspaceCard.jsx — datapoint component (tool-workspace_card, UI-JOURNEY-1 B3).
   What one workspace holds, from GET /v1/workspaces/{name}/resources: the cases by split (and
   the importer that loaded them), the runs, the grade jobs with their round, the pinned demo
   sets with the pin gate's held-out score, the corrections log, the exports, the per-role
   provider bindings (never a key) and the arm manifest. Counts and names only; an empty output
   is an honest "no workspace loaded yet", never a fabricated inventory. */
import { registerTool } from "./registry.js";

const n = (x) => (x == null ? "—" : Number(x).toLocaleString());

function Row({ label, children, testid }) {
  return (
    <div className="flex items-baseline gap-3 py-1 border-b border-border/60 last:border-0" data-testid={testid}>
      <span className="w-28 shrink-0 text-[11px] uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className="text-[12.5px] leading-snug">{children}</span>
    </div>
  );
}

export default function WorkspaceCard({ name, pack, agent, cases, runs, jobs = [], pinned_demos = {}, corrections, exports = [], bindings, arm_manifest } = {}) {
  if (!name) {
    return (
      <div className="rounded-[var(--radius)] border border-border bg-card p-3 text-[12.5px] text-muted-foreground" data-testid="workspace-card-empty">
        No workspace loaded yet.
      </div>
    );
  }
  const splits = Object.entries((cases && cases.by_split) || {});
  const roles = Object.entries((bindings && bindings.roles) || {});
  const demos = Object.entries(pinned_demos || {});
  return (
    <div className="rounded-[var(--radius)] border border-border bg-card p-3" data-testid="workspace-card">
      <div className="mb-2 flex items-baseline justify-between">
        <div className="text-[13px] font-semibold">Workspace · {name}</div>
        <div className="font-mono text-[10.5px] text-muted-foreground">{pack}{agent ? ` · ${agent}` : ""}</div>
      </div>
      <Row label="Cases" testid="workspace-cases">
        {n(cases && cases.total)}
        {splits.length > 0 && <span className="text-muted-foreground"> ({splits.map(([s, c]) => `${s} ${c}`).join(", ")})</span>}
        {cases && cases.importer && <span className="text-muted-foreground"> · loaded by {cases.importer}</span>}
      </Row>
      <Row label="Runs" testid="workspace-runs">{n(runs)}</Row>
      <Row label="Grade jobs" testid="workspace-jobs">
        {jobs.length === 0 ? <span className="text-muted-foreground">none yet</span> : jobs.map((j) => (
          <span key={j.job_id} className="mr-3 inline-block">
            <span className="font-mono">{j.job_id}</span>{j.round ? ` · ${j.round}` : ""} · {j.status} {j.done != null ? `${j.done}/${j.total}` : ""}
          </span>
        ))}
      </Row>
      <Row label="Pinned demos" testid="workspace-demos">
        {demos.length === 0 ? <span className="text-muted-foreground">none pinned</span> : demos.map(([role, d]) => (
          <span key={role} className="mr-3 inline-block">{role}: {n(d.demos)} demos{d.graded != null ? `, held-out graded ${Number(d.graded).toFixed(2)}` : ""}</span>
        ))}
      </Row>
      <Row label="Corrections" testid="workspace-corrections">
        {corrections ? `${n(corrections.records)} records, ${n(corrections.gold_mismatches)} gold mismatches` : "—"}
      </Row>
      <Row label="Exports" testid="workspace-exports">
        {exports.length === 0 ? <span className="text-muted-foreground">none yet</span> : exports.map((e) => (
          <span key={e.name} className="mr-3 inline-block font-mono">{e.name}{e.rows != null ? ` (${e.rows} rows)` : ""}</span>
        ))}
      </Row>
      <Row label="Bindings" testid="workspace-bindings">
        {roles.length === 0 ? <span className="text-muted-foreground">no role bound</span> : roles.map(([role, b]) => (
          <span key={role} className="mr-3 inline-block">{role}: {b && b.provider ? `${b.provider}/${b.model || "?"}` : "unbound"}</span>
        ))}
      </Row>
      <Row label="Arm" testid="workspace-arm">
        {arm_manifest ? `${arm_manifest.model || "?"}${arm_manifest.azure_model_version ? ` (served ${arm_manifest.azure_model_version})` : ""}` : <span className="text-muted-foreground">no arm manifest</span>}
      </Row>
    </div>
  );
}

registerTool("tool-workspace_card", WorkspaceCard);
