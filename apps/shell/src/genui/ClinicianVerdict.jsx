/* ClinicianVerdict.jsx — META-VERDICT-1 / CONV-FIRST: the clinician's INDEPENDENT verdict +
   judge meta-audit on a run (Clinical Scribe Review Layer-3, the HITL clinical validator). A physician
   records their own pass/fail, whether they AGREE with the council, and — on dissent — the
   judge's named fallacy + rationale. It POSTs one immutable, audited AuditRecord; it NEVER
   changes the verdict and never fires a paid run.

   SHARED so it renders BOTH inline (the VerdictCard, in the conversation — the conversational-
   first working surface) AND in the pane (artifact.jsx ReportTab — the drill-down). Parametrized
   by {runId, councilVerdict} (NOT the whole runResult) so the inline card can pass the projected
   verdict_part fields straight through. [[SPEC_CONVERSATIONAL_FIRST]] */
import { useState } from "react";
import { recordMetaVerdict } from "../bff.js";
import { friendlyError } from "./copy.js";

// META-VERDICT-1: the closed judge-fallacy taxonomy (Clinical Scribe Review's "Judge Fallacy" column) —
// a clinician naming WHY the automated judge erred. Mirrors the BFF's JudgeFallacyCode enum.
export const JUDGE_FALLACIES = [
  "Hallucination Blindness",
  "Reference Bias",
  "Metric Conflation",
  "Risk-Severity Blindness",
  "Boundary Violation",
];

export default function ClinicianVerdict({ runId, councilVerdict }) {
  const [hv, setHv] = useState("fail");
  const [agrees, setAgrees] = useState(false);
  const [fallacy, setFallacy] = useState("");
  const [rationale, setRationale] = useState("");
  const [save, setSave] = useState({ state: "idle", msg: "" }); // idle|saving|saved|error

  if (!runId)
    return (
      <div className="art-sec" data-testid="clinician-verdict" style={{ marginTop: 4 }}>
        <div className="art-h2">Clinician verdict <span className="cnt">your independent review</span></div>
        <div style={{ fontSize: 12.5, color: "var(--muted)" }}>
          Run an evaluation first — your verdict attaches to a specific run.
        </div>
      </div>
    );

  async function submit() {
    setSave({ state: "saving", msg: "" });
    try {
      await recordMetaVerdict({
        run_id: runId,
        human_verdict: hv,
        agrees_with_council: agrees,
        ...(!agrees && fallacy ? { judge_fallacy_code: fallacy } : {}),
        rationale,
      });
      setSave({ state: "saved", msg: "Recorded — immutable + audited." });
    } catch (e) {
      setSave({ state: "error", msg: friendlyError(e) });
    }
  }

  const seg = (val, label, color) => (
    <button type="button"
      className={"btn " + (hv === val ? "btn-primary" : "btn-ghost")}
      style={{ padding: "5px 12px", ...(hv === val ? { background: color, boxShadow: "none" } : {}) }}
      onClick={() => setHv(val)}>{label}</button>
  );
  const field = { fontFamily: "inherit", fontSize: 12.5, padding: "6px 8px", borderRadius: 8, border: "1px solid var(--border)", background: "var(--bg)", color: "var(--ink)" };

  return (
    <div className="art-sec" data-testid="clinician-verdict" style={{ marginTop: 4 }}>
      <div className="art-h2">Clinician verdict <span className="cnt">your independent review</span></div>
      <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 10 }}>
        Record your own call on this run — kept as an immutable, audited attestation. It never changes the verdict.
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12, fontSize: 12.5 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
          <span>Your verdict</span>
          <div style={{ display: "flex", gap: 6 }}>
            {seg("pass", "Pass", "var(--teal)")}
            {seg("fail", "Fail", "var(--accent)")}
          </div>
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
          <input type="checkbox" checked={agrees} onChange={(e) => setAgrees(e.target.checked)} />
          <span>I agree with the council{councilVerdict ? ` (${councilVerdict})` : ""}</span>
        </label>
        {!agrees && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
            <span>The judge’s fallacy</span>
            <select aria-label="Judge fallacy" value={fallacy} onChange={(e) => setFallacy(e.target.value)} style={{ ...field, minWidth: 210 }}>
              <option value="">— name it (optional) —</option>
              {JUDGE_FALLACIES.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
        )}
        <textarea aria-label="Rationale" value={rationale} onChange={(e) => setRationale(e.target.value)}
          placeholder="Why? (the clinical rationale a regulator can read)" rows={2}
          style={{ ...field, width: "100%", boxSizing: "border-box", resize: "vertical" }} />
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button type="button" className="btn btn-primary" onClick={submit} disabled={save.state === "saving"}>
            {save.state === "saving" ? "Saving…" : save.state === "saved" ? "Recorded ✓" : "Record verdict"}
          </button>
          {save.msg && (
            <span style={{ fontSize: 11.5, color: save.state === "error" ? "var(--accent)" : "var(--teal)" }}>{save.msg}</span>
          )}
        </div>
      </div>
    </div>
  );
}
