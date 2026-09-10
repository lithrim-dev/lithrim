/* ImportCard.jsx — datapoint + write component (tool-import_cases, UI-JOURNEY-1 B4).
   The Load verb from the shell: pick one of the importers the workspace's pack declares (a
   kind:importer manifest — the dataset's vocabulary, its citation and licence, the adapter that
   turns its files into cases), hand it the dataset's own files, size the cut, and load the test
   and calibration splits into the workspace with labels kept. POST /v1/cases/import is $0 (no
   model call); the result line reports exactly what landed, never a claimed count. */
import { useEffect, useState } from "react";
import { importCases, listImporters } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { friendlyError } from "./copy.js";
import { registerTool } from "./registry.js";

export default function ImportCard({ importers: given = null, agent = "ws0_default", onLoaded }) {
  const [importers, setImporters] = useState(given || []);
  const [pick, setPick] = useState((given && given[0] && given[0].id) || "");
  const [files, setFiles] = useState({});
  const [perTask, setPerTask] = useState(30);
  const [splits, setSplits] = useState({ test: true, calibration: true });
  const [state, setState] = useState({ phase: "idle", msg: "", result: null }); // idle|busy|loaded|error

  useEffect(() => {
    if (given) return;
    listImporters().then((r) => {
      const list = r.importers || [];
      setImporters(list);
      if (list[0] && !pick) setPick(list[0].id);
    }).catch(() => {});
  }, [given]); // eslint-disable-line react-hooks/exhaustive-deps

  const imp = importers.find((i) => i.id === pick) || null;
  const needed = (imp && imp.files) || [];
  const ready = imp && imp.adapter && needed.every((f) => files[f] != null) && (splits.test || splits.calibration);

  const readFile = (name, file) => {
    if (!file) return;
    file.text().then((text) => setFiles((f) => ({ ...f, [name]: text }))).catch((e) => setState({ phase: "error", msg: friendlyError(e), result: null }));
  };

  const load = async () => {
    if (!ready) return;
    setState({ phase: "busy", msg: "", result: null });
    try {
      const res = await importCases({
        agent, importer: imp.id, files, per_task: Number(perTask) || 30,
        splits: ["test", "calibration"].filter((s) => splits[s]),
      });
      const parts = Object.entries(res.imported || {}).map(([s, n]) => `${n} ${s}`);
      setState({ phase: "loaded", msg: `loaded ${parts.join(" + ")} cases from ${res.dataset} (labels kept, tagged by split)`, result: res });
      onLoaded?.(res);
      try { window.dispatchEvent(new CustomEvent("lithrim:cases-changed", { detail: res })); } catch {}
    } catch (e) {
      setState({ phase: "error", msg: friendlyError(e), result: null });
    }
  };

  const field = "rounded-[var(--radius-sm)] border border-border bg-background px-2 py-1 text-[12.5px]";
  return (
    <div className="rounded-[var(--radius)] border border-border bg-card p-3" data-testid="import-cases">
      <div className="mb-1 text-[13px] font-semibold">Load a dataset</div>
      <div className="mb-2 text-[12px] text-muted-foreground">
        A dataset importer maps the dataset's own labels onto this pack's checks and says which adapter turns its files into cases. The cut is stratified per task; labels are kept, and every case is tagged with its split so a later step can grade one split and calibrate on the other.
      </div>
      {importers.length === 0 ? (
        <div className="text-[12.5px] text-muted-foreground" data-testid="import-no-importers">This pack declares no dataset importer.</div>
      ) : (
        <div className="flex flex-col gap-2">
          <label className="flex items-center gap-2 text-[12.5px]">
            <span className="w-24 shrink-0 text-muted-foreground">Importer</span>
            <select className={field} value={pick} onChange={(e) => { setPick(e.target.value); setFiles({}); }} data-testid="import-importer">
              {importers.map((i) => <option key={i.id} value={i.id}>{i.dataset} · {i.id}</option>)}
            </select>
          </label>
          {imp && (
            <div className="text-[11.5px] text-muted-foreground" data-testid="import-provenance">
              {imp.citation ? `${imp.citation}. ` : ""}{imp.license ? `Licence: ${imp.license}. ` : ""}
              {imp.verdict_rule && imp.verdict_rule[imp.dataset] ? `Verdict rule (${imp.dataset}): ${imp.verdict_rule[imp.dataset]}.` : ""}
              {!imp.adapter && " This importer declares no adapter, so its files cannot be loaded here."}
            </div>
          )}
          {needed.map((name) => (
            <label key={name} className="flex items-center gap-2 text-[12.5px]">
              <span className="w-24 shrink-0 font-mono text-[11px]">{name}</span>
              <input type="file" accept=".jsonl,.json,.csv,.txt" onChange={(e) => readFile(name, e.target.files && e.target.files[0])} />
              {files[name] != null && <span className="text-[11px] text-muted-foreground">read</span>}
            </label>
          ))}
          <div className="flex flex-wrap items-center gap-3 text-[12.5px]">
            <label className="flex items-center gap-2">
              <span className="text-muted-foreground">Per task</span>
              <input type="number" min="1" className={`${field} w-20`} value={perTask} onChange={(e) => setPerTask(e.target.value)} data-testid="import-per-task" />
            </label>
            {["test", "calibration"].map((s) => (
              <label key={s} className="flex items-center gap-1">
                <input type="checkbox" checked={!!splits[s]} onChange={(e) => setSplits((v) => ({ ...v, [s]: e.target.checked }))} data-testid={`import-split-${s}`} /> {s}
              </label>
            ))}
            <Button size="sm" onClick={load} disabled={!ready || state.phase === "busy"} data-testid="import-load">
              {state.phase === "busy" ? "Loading…" : "Load"}
            </Button>
          </div>
          {state.msg && (
            <div className={`text-[12px] ${state.phase === "error" ? "text-destructive" : "text-muted-foreground"}`} data-testid="import-result">
              {state.phase === "error" ? "⚠ " : "✓ "}{state.msg}
            </div>
          )}
          {state.phase === "loaded" && state.result && (state.result.imported || {}).test > 0 && (
            <div className="flex items-center gap-2 text-[12px]">
              <span className="text-muted-foreground">Next: grade the test split as the before round.</span>
              <Button size="sm" variant="outline" data-testid="import-grade-test"
                onClick={() => { try { window.dispatchEvent(new CustomEvent("lithrim:grade-cohort", { detail: { split: "test", round: "before" } })); } catch {} }}>
                Grade the test split (paid)
              </Button>
            </div>
          )}
          {state.phase === "loaded" && state.result && (state.result.imported || {}).calibration > 0 && (
            <div className="flex items-center gap-2 text-[12px]">
              <span className="text-muted-foreground">For a training export: grade the calibration split too.</span>
              <Button size="sm" variant="outline" data-testid="import-grade-calibration"
                onClick={() => { try { window.dispatchEvent(new CustomEvent("lithrim:grade-cohort", { detail: { split: "calibration", round: "calibration" } })); } catch {} }}>
                Grade the calibration split (paid)
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

registerTool("tool-import_cases", ImportCard);
