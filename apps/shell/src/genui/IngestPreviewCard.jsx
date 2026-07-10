/* IngestPreviewCard — CE-INGEST-FRONTDOOR-1: the inline front door for loading eval cases from an
   uploaded JSON / JSONL / CSV file.

   The composer's attach button POSTs the blob to /v1/cases/ingest/preview and injects this card —
   either with the preview result (success) OR with an `error` (the extractor didn't converge). The
   card shows the detected mapping + a peek at the extracted cases and lets the human:
     • APPROVE → /commit pins the template + upserts the corpus,
     • CORRECT → edit the field-mapping rule + re-preview (the "ask the user the fields" path),
     • RECOVER → on a failed preview, the SAME rules box + Retry (so any arbitrary shape is
       recoverable in-UI, not a dead end).
   Honors conversational-first: the file picker is the only chrome; validate→approve→loaded is all
   inline gen-UI. Nothing is pinned/written until Approve. */
import { useState } from "react";
import { ingestPreview, ingestCommit } from "../bff.js";
import { Button } from "../components/ui/button.jsx";
import { Icon } from "../icons.jsx";
import { friendlyError } from "./copy.js";
import { registerTool } from "./registry.js";

const FMT_LABEL = { json: "JSON", jsonl: "JSONL", csv: "CSV", auto: "file" };

function clip(s, n = 80) {
  const t = String(s ?? "");
  return t.length > n ? t.slice(0, n) + "…" : t;
}

export default function IngestPreviewCard({
  fmt = "auto", columns = [], count = 0, sample_cases = [], template = "",
  raw = "", filename = "", agent = "ws0_default", extraction_rules = "", error = "",
  onResult, onLoaded,
}) {
  // local, self-contained state — correcting the mapping / retrying a failure never leaves the card
  const [prev, setPrev] = useState({ fmt, columns, count, sample_cases, template });
  const [rules, setRules] = useState(extraction_rules);
  const [state, setState] = useState({ phase: error ? "error" : "preview", msg: error || "" }); // preview|busy|loaded|error
  const [editRules, setEditRules] = useState(!!error); // a hard failure opens the rules box

  const fmtLabel = FMT_LABEL[prev.fmt] || prev.fmt;
  const busy = state.phase === "busy";

  const rePreview = async () => {
    setState({ phase: "busy", msg: "" });
    try {
      const res = await ingestPreview({ raw, fmt, filename, extraction_rules: rules, agent });
      setPrev({ fmt: res.fmt, columns: res.columns || [], count: res.count, sample_cases: res.sample_cases || [], template: res.template });
      setEditRules(false);
      setState({ phase: "preview", msg: "" });
    } catch (e) {
      setState({ phase: "error", msg: friendlyError(e) });
      setEditRules(true);
    }
  };

  const approve = async () => {
    setState({ phase: "busy", msg: "" });
    try {
      const res = await ingestCommit({ approved_template: prev.template, raw, fmt, filename, extraction_rules: rules, agent });
      setState({ phase: "loaded", msg: `${res.count} case${res.count === 1 ? "" : "s"} loaded into the corpus` });
      onLoaded?.(res);
      onResult?.({ ingested: res.count, mapping_id: res.mapping_id });
    } catch (e) {
      setState({ phase: "error", msg: friendlyError(e) });
    }
  };

  // the rules editor — shared by the "Mapping looks wrong?" correction and the failure-recovery retry
  const rulesEditor = (retryLabel) => (
    <div className="mt-2">
      <textarea
        data-testid="ingest-rules"
        rows="2"
        className="w-full rounded-[var(--radius-sm)] border border-border bg-secondary px-2 py-1.5 text-[11px] outline-none focus-visible:border-primary"
        placeholder="Describe the fields, e.g. 'one case per `episodes`; response = outbound.message.body, context = inbound.text, case_id = eid'"
        value={rules}
        onChange={(e) => setRules(e.target.value)}
      />
      <div className="mt-1.5 flex gap-2">
        <Button data-testid="ingest-retry" size="sm" onClick={rePreview} disabled={busy || !raw}>{busy ? "Re-reading…" : retryLabel}</Button>
        {prev.count > 0 && <Button size="sm" variant="ghost" onClick={() => setEditRules(false)} disabled={busy}>Cancel</Button>}
      </div>
    </div>
  );

  // ── loaded ──
  if (state.phase === "loaded") {
    return (
      <div data-testid="ingest-preview-card" className="rounded-[var(--radius)] border border-border bg-background p-3.5 text-xs">
        <div className="flex items-center gap-2 font-[family-name:var(--font-mono)] text-[13px] font-semibold" style={{ color: "var(--teal)" }}>
          <Icon name="check" size={14} /> {state.msg}
        </div>
        <div className="mt-1.5 text-[11px] text-muted-foreground">
          They're in this workspace's corpus now — ask Lithrim to <strong>grade all cases</strong> (you'll confirm the cost).
        </div>
      </div>
    );
  }

  // ── hard failure (no cases extracted): the recovery UI — message + rules box + Retry, never a dead end ──
  if (state.phase === "error" && !prev.count) {
    return (
      <div data-testid="ingest-preview-card" className="rounded-[var(--radius)] border border-border bg-background p-3.5 text-xs">
        <div className="flex items-center gap-2 font-[family-name:var(--font-mono)] text-[13px] font-semibold" style={{ color: "var(--accent-ink)" }}>
          <Icon name="flag" size={14} /> Couldn't map {filename ? clip(filename, 28) : "this file"} into cases
        </div>
        <div className="mt-1 text-[11px] text-muted-foreground">
          {state.msg || "The extractor didn't converge on this shape."} Describe the fields and retry — name the record collection and which field is the response vs the context.
        </div>
        {rulesEditor("Retry")}
      </div>
    );
  }

  // ── preview (has cases) ──
  return (
    <div data-testid="ingest-preview-card" className="rounded-[var(--radius)] border border-border bg-background p-3.5 text-xs">
      <div className="flex items-center justify-between">
        <div className="font-[family-name:var(--font-mono)] text-[13px] font-semibold text-foreground">
          {prev.count} case{prev.count === 1 ? "" : "s"} from {fmtLabel}{filename ? ` · ${clip(filename, 32)}` : ""}
        </div>
        <span className="text-[10px] text-muted-foreground">preview · nothing saved yet</span>
      </div>

      {prev.columns?.length > 0 && (
        <div className="mt-1.5 text-[11px] text-muted-foreground">
          columns: {prev.columns.map((c) => <span key={c} className="font-[family-name:var(--font-mono)]">{c}{" "}</span>)}
        </div>
      )}

      <div className="mt-2 flex flex-col gap-1">
        {(prev.sample_cases || []).map((c, i) => (
          <div key={c.case_id || i} className="rounded-[var(--radius-sm)] border border-border bg-secondary px-2.5 py-1.5">
            <div className="font-[family-name:var(--font-mono)] text-[11px] text-foreground">{c.case_id || `(row ${i + 1})`}</div>
            {c.response != null && <div className="mt-0.5 text-[10.5px] text-muted-foreground"><span style={{ color: "var(--ink)" }}>response:</span> {clip(c.response)}</div>}
            {c.context != null && <div className="text-[10.5px] text-muted-foreground"><span style={{ color: "var(--ink)" }}>context:</span> {clip(c.context)}</div>}
          </div>
        ))}
        {prev.count > (prev.sample_cases || []).length && (
          <div className="text-[10.5px] text-muted-foreground">…and {prev.count - (prev.sample_cases || []).length} more</div>
        )}
      </div>

      {/* the GENERATED JUTE template — the transform that maps your JSON → cases (verify before approve) */}
      {prev.template && (
        <details data-testid="ingest-template" className="mt-2.5">
          <summary className="cursor-pointer text-[10.5px] text-muted-foreground select-none">View the generated JUTE template ▸</summary>
          <pre className="mt-1.5 max-h-48 overflow-auto rounded-[var(--radius-sm)] border border-border bg-secondary px-2.5 py-2 text-[10.5px] font-[family-name:var(--font-mono)] whitespace-pre-wrap text-foreground">{prev.template}</pre>
        </details>
      )}

      {state.phase === "error" && (
        <div className="mt-2 text-[11px]" style={{ color: "var(--accent-ink)" }}>⚠ {state.msg}</div>
      )}

      {editRules ? rulesEditor("Re-preview") : (
        <div className="mt-3 flex items-center gap-2">
          <Button data-testid="ingest-approve" size="sm" onClick={approve} disabled={busy || !prev.count}
            title={!prev.count ? "No cases parsed yet — fix the field mapping above first" : undefined}>
            {busy ? "Loading…" : `Approve & load ${prev.count} case${prev.count === 1 ? "" : "s"}`}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setEditRules(true)} disabled={busy}>Mapping looks wrong?</Button>
        </div>
      )}
    </div>
  );
}

registerTool("tool-ingest_preview", IngestPreviewCard);
