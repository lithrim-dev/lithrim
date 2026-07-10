/* RunLineage.jsx — the shared run-lineage affordances (RUNTRAIL-8/9). For one run: a History
   expander (getRunHistory → prior versions) + a $0 Rehydrate (rehydrateRun → reconstructed
   verdict). Extracted from the near-identical RunPanel.HistoryRow + AuditView.RunLineage so there
   is ONE source for both consumers.

   Each async action shows a PENDING state (disabled + "Loading…"/"Rehydrating…") so the click
   registers immediately — the prior duplicated copies awaited with no feedback (a dead-click). */
import { useState } from "react";
import { getRunHistory, rehydrateRun } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { verdictLabel, gradeTag } from "./copy.js";

const verdictTone = (v) => (v === "BLOCK" ? "var(--accent-ink)" : "var(--teal)");

export default function RunLineage({ runId, className = "" }) {
  const [versions, setVersions] = useState(null); // null = collapsed; [] = loaded-empty
  const [rehydrated, setRehydrated] = useState(null);
  const [histBusy, setHistBusy] = useState(false);
  const [rehyBusy, setRehyBusy] = useState(false);

  const toggleHistory = async () => {
    if (versions !== null) { setVersions(null); return; }
    setHistBusy(true);
    try { setVersions((await getRunHistory(runId)).history || []); }
    catch { setVersions([]); }
    finally { setHistBusy(false); }
  };
  const doRehydrate = async () => {
    setRehyBusy(true);
    try { setRehydrated(await rehydrateRun(runId)); }
    catch { setRehydrated({ verdict: null }); }
    finally { setRehyBusy(false); }
  };

  return (
    <div className={"flex flex-col gap-1 " + className}>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="ghost" className="h-5 px-1.5 text-[10px]" onClick={toggleHistory} disabled={histBusy}>
          {histBusy ? "Loading…" : "History"}
        </Button>
        <Button size="sm" variant="ghost" className="h-5 px-1.5 text-[10px]" onClick={doRehydrate} disabled={rehyBusy}>
          {rehyBusy ? "Rehydrating…" : "Rehydrate $0"}
        </Button>
      </div>
      {versions !== null && (
        <div className="ml-3 flex flex-col gap-0.5">
          {versions.length === 0 && <span className="text-[10px] text-muted-foreground">No prior versions.</span>}
          {versions.map((v, i) => (
            <div key={i} className="flex items-center gap-2 text-[10px]" data-testid="history-version">
              <span className="font-[family-name:var(--font-mono)] text-muted-foreground">{(v.run_id || "").slice(0, 8)}</span>
              <span style={{ color: verdictTone(v.verdict) }}>{verdictLabel(v.verdict)}</span>
              {v.grade_path && <span className="text-muted-foreground">{gradeTag(v.grade_path)}</span>}
            </div>
          ))}
        </div>
      )}
      {rehydrated && (
        <div className="ml-3 text-[10px]" data-testid="rehydrated-verdict">
          Rehydrated: <span style={{ color: verdictTone(rehydrated.verdict) }}>{verdictLabel(rehydrated.verdict)}</span>
        </div>
      )}
    </div>
  );
}
