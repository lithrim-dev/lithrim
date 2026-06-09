/* CaseCard.jsx — the inline Case Summary card (CHATBIND-3 / tool-case_summary).
   show_case emits a { agent } reference; this card SELF-FETCHES GET /v1/case (the
   reference-carrying pattern, like AgentEditor/JudgeEditor) and renders a summary of the
   SOURCE case the council grades — case_id, the by-construction planted defect, a note/transcript
   snippet — with a "View case ->" that opens the full Case tab. $0/read, no paid path.

   Prop convention (S-BS-19): renderTool spreads part.output as props, so `agent` arrives flat;
   `onOpenArtifact` is passed as a handler by panes.jsx. */
import { useEffect, useState } from "react";
import { Icon } from "../icons.jsx";
import { registerTool } from "./registry.js";
import { getCase } from "../bff.js";

export default function CaseCard({ agent = "ws0_default", onOpenArtifact } = {}) {
  const [kase, setKase] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    let live = true;
    getCase(agent)
      .then((c) => { if (live) setKase(c); })
      .catch((e) => { if (live) setErr(String(e.message || e)); });
    return () => { live = false; };
  }, [agent]);

  if (err)
    return <div className="icard"><div className="icard-bd" style={{ color: "var(--accent)" }}>Could not load the case: {err}</div></div>;
  if (!kase)
    return <div className="icard"><div className="icard-bd" style={{ color: "var(--muted)" }}>Loading the case…</div></div>;

  const planted = kase.expected_safety_flags || [];
  const snippet = (kase.artifact_text || kase.transcript || "").trim().slice(0, 180);
  return (
    <div className="icard">
      <div className="icard-hd">
        <span className="ic"><Icon name="panel" size={15} /></span>
        <span className="ttl">Source case</span>
        <span className="sub">{kase.case_id}</span>
        <span className="right"><span className="chip">{planted.length ? `${planted.length} planted` : "clean"}</span></span>
      </div>
      <div className="icard-bd">
        <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 10, lineHeight: 1.5 }}>
          {snippet}{snippet.length >= 180 ? "…" : ""}
        </div>
        {planted.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
            {planted.map((f) => <span key={f} className="chip">{f}</span>)}
          </div>
        )}
        <button className="btn btn-ghost" onClick={() => onOpenArtifact?.("case")}>
          View case <Icon name="chevR" size={13} />
        </button>
      </div>
    </div>
  );
}

registerTool("tool-case_summary", CaseCard);
