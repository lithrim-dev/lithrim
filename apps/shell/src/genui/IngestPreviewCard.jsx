/* IngestPreviewCard — CE-INGEST-FRONTDOOR-1 (Stage 2): the inline front door for loading eval
   cases from an uploaded JSON / JSONL / CSV file.

   The composer's attach button POSTs the blob to /v1/cases/ingest/preview and injects this card
   with the preview result. The card shows the detected field mapping + a peek at the extracted
   cases, and lets the human:
     • APPROVE → /commit pins the template + upserts the corpus (the cases become gradeable),
     • CORRECT → edit the field-mapping rule + re-preview (the "ask the user the fields" path),
   honoring the conversational-first invariant: the file picker is the only chrome; the
   validate→approve→loaded flow is all inline gen-UI. Nothing is pinned/written until Approve. */
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
  raw = "", filename = "", agent = "ws0_default", extraction_rules = "",
  onResult, onLoaded,
}) {
  // local, self-contained re-preview state (correcting the mapping never leaves the card)
  const [prev, setPrev] = useState({ fmt, columns, count, sample_cases, template });
  const [rules, setRules] = useState(extraction_rules);
  const [state, setState] = useState({ phase: "preview", msg: "" }); // preview|busy|loaded|error
  const [editRules, setEditRules] = useState(false);

  const fmtLabel = FMT_LABEL[prev.fmt] || prev.fmt;

  const rePreview = async () => {
    setState({ phase: "busy", msg: "" });
    try {
      const res = await ingestPreview({ raw, fmt, filename, extraction_rules: rules, agent });
      setPrev({ fmt: res.fmt, columns: res.columns || [], count: res.count, sample_cases: res.sample_cases || [], template: res.template });
      setEditRules(false);
      setState({ phase: "preview", msg: "" });
    } catch (e) {
      setState({ phase: "error", msg: friendlyError(e) });
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

  if (state.phase === "loaded") {
    return (
      <div data-testid="ingest-preview-card" className="rounded-[var(--radius)] border border-border bg-background p-3.5 text-xs">
        <div className="flex items-center gap-2 font-[family-name:var(--font-mono)] text-[13px] font-semibold" style={{ color: "var(--teal)" }}>
          <Icon name="check" size={14} /> {state.msg}
        </div>
        <div className="mt-1.5 text-[11px] text-muted-foreground">
          They're in this workspace's corpus now — use <strong>Run all</strong> to grade them.
        </div>
      </div>
    );
  }

  const busy = state.phase === "busy";

  return (
    <div data-testid="ingest-preview-card" className="rounded-[var(--radius)] border border-border bg-background p-3.5 text-xs">
      {/* ── headline ── */}
      <div className="flex items-center justify-between">
        <div className="font-[family-name:var(--font-mono)] text-[13px] font-semibold text-foreground">
          {prev.count} case{prev.count === 1 ? "" : "s"} from {fmtLabel}{filename ? ` · ${clip(filename, 32)}` : ""}
        </div>
        <span className="text-[10px] text-muted-foreground">preview · nothing saved yet</span>
      </div>

      {/* CSV columns (the source fields, for the mapping confirm) */}
      {prev.columns?.length > 0 && (
        <div className="mt-1.5 text-[11px] text-muted-foreground">
          columns: {prev.columns.map((c) => <span key={c} className="font-[family-name:var(--font-mono)]">{c}{" "}</span>)}
        </div>
      )}

      {/* ── a peek at the extracted cases (case_id → response / context) ── */}
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

      {/* the GENERATED JUTE template — the transform that maps your JSON → cases (verify before approve).
          The mapper executes JUTE; the model only authors it. Collapsed by default. */}
      {prev.template && (
        <details data-testid="ingest-template" className="mt-2.5">
          <summary className="cursor-pointer text-[10.5px] text-muted-foreground select-none">View the generated JUTE template ▸</summary>
          <pre className="mt-1.5 max-h-48 overflow-auto rounded-[var(--radius-sm)] border border-border bg-secondary px-2.5 py-2 text-[10.5px] font-[family-name:var(--font-mono)] whitespace-pre-wrap text-foreground">{prev.template}</pre>
        </details>
      )}

      {state.phase === "error" && (
        <div className="mt-2 text-[11px]" style={{ color: "var(--accent-ink)" }}>⚠ {state.msg}</div>
      )}

      {/* ── correction channel: describe the right fields → re-preview ── */}
      {editRules ? (
        <div className="mt-2.5">
          <textarea
            data-testid="ingest-rules"
            rows="2"
            className="w-full rounded-[var(--radius-sm)] border border-border bg-secondary px-2 py-1.5 text-[11px] outline-none focus-visible:border-primary"
            placeholder="Describe the fields, e.g. 'use the summary column as response and conversation as context'"
            value={rules}
            onChange={(e) => setRules(e.target.value)}
          />
          <div className="mt-1.5 flex gap-2">
            <Button size="sm" variant="secondary" onClick={rePreview} disabled={busy}>{busy ? "Re-reading…" : "Re-preview"}</Button>
            <Button size="sm" variant="ghost" onClick={() => setEditRules(false)} disabled={busy}>Cancel</Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex items-center gap-2">
          <Button data-testid="ingest-approve" size="sm" onClick={approve} disabled={busy || !prev.count}>
            {busy ? "Loading…" : `Approve & load ${prev.count} case${prev.count === 1 ? "" : "s"}`}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setEditRules(true)} disabled={busy}>Mapping looks wrong?</Button>
        </div>
      )}
    </div>
  );
}

registerTool("tool-ingest_preview", IngestPreviewCard);
