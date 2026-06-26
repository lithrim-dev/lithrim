/* CaseCard.jsx — the inline Case Summary card (CHATBIND-3 / tool-case_summary).
   show_case emits a { agent, case_id } reference; this card SELF-FETCHES GET /v1/case and renders
   the SOURCE case the council grades INLINE in the conversation: the visit transcript (Visit) AND the
   scribe note (Note), side by side, so the human compares WHAT WAS SAID vs WHAT WAS DOCUMENTED — the
   gap (a refusal said but erased from the note) is legible in the chat, not behind a pane click
   (INLINE-IMPACT-1). A long case expands inline; "Open transcript editor" is an OPTIONAL drill-down
   for the raw/editable surface, never the way to read the case. $0/read, no paid path.

   NARR-CHAT-LOOP: `case_id` (from show_case) selects the SPECIFIC ingested case; `null` keeps the
   agent's own dataset.case_id. Prop convention (S-BS-19): renderTool spreads part.output as props. */
import { useEffect, useState } from "react";
import { Icon } from "../icons.jsx";
import { registerTool } from "./registry.js";
import { getCase } from "../bff.js";

const CUT = 200; // collapsed chars per pane — enough to read the gist + the gap, not the whole note

export default function CaseCard({ agent = "ws0_default", case_id = null, onOpenArtifact } = {}) {
  const [kase, setKase] = useState(null);
  const [err, setErr] = useState(null);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    let live = true;
    getCase(agent, case_id)
      .then((c) => { if (live) setKase(c); })
      .catch((e) => { if (live) setErr(String(e.message || e)); });
    return () => { live = false; };
  }, [agent, case_id]);

  if (err)
    return <div className="icard"><div className="icard-bd" style={{ color: "var(--accent)" }}>We couldn't load this case. Please try again.</div></div>;
  if (!kase)
    return <div className="icard"><div className="icard-bd" style={{ color: "var(--muted)" }}>Loading the case…</div></div>;

  const planted = kase.expected_safety_flags || [];
  const visit = (kase.transcript || "").trim();
  const note = (kase.artifact_text || kase.artifact || "").trim();
  const clip = (s) => (expanded || s.length <= CUT ? s : s.slice(0, CUT).trimEnd() + "…");
  const hasMore = visit.length > CUT || note.length > CUT;
  const lbl = { fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, color: "var(--muted)", marginBottom: 3 };
  const body = { fontSize: 12.5, color: "var(--fg)", lineHeight: 1.5, whiteSpace: "pre-wrap" };
  return (
    <div className="icard">
      <div className="icard-hd">
        <span className="ic"><Icon name="panel" size={15} /></span>
        <span className="ttl">Source case</span>
        <span className="sub">{kase.case_id}</span>
        <span className="right"><span className="chip">{planted.length ? `${planted.length} planted` : "clean"}</span></span>
      </div>
      <div className="icard-bd">
        {visit && (
          <div style={{ marginBottom: 9 }}>
            <div style={lbl}>Visit</div>
            <div style={body}>{clip(visit)}</div>
          </div>
        )}
        {note && (
          <div style={{ marginBottom: 9 }}>
            <div style={lbl}>Note</div>
            <div style={body}>{clip(note)}</div>
          </div>
        )}
        {planted.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, margin: "8px 0" }}>
            {planted.map((f) => <span key={f} className="chip">{f}</span>)}
          </div>
        )}
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 6 }}>
          {hasMore && (
            <button className="btn btn-ghost" onClick={() => setExpanded(!expanded)}>
              {expanded ? "Show less" : "Show full case"}
            </button>
          )}
          {onOpenArtifact && (
            <button className="btn btn-ghost" style={{ color: "var(--muted)" }} onClick={() => onOpenArtifact("case")}>
              Open transcript editor <Icon name="chevR" size={13} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

registerTool("tool-case_summary", CaseCard);
