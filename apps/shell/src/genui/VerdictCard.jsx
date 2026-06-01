/* VerdictCard.jsx — datapoint component (tool-verdict_card, SPEC §5b).
   Promoted from cards.jsx into the gen-UI registry. Kept visually faithful on the
   existing .icard chrome CSS (incremental adoption, SPEC §4 — the bespoke CSS is
   not rewritten into utilities); the foundation is exercised by the D2 input
   widgets. Accepts an optional datapoint via part.output; defaults to the demo. */
import { Icon } from "../icons.jsx";
import { registerTool } from "./registry.js";

const DEMO = {
  id: "#1843 · dry run",
  question: "Patient denies any drug allergies; the visit covers a knee-pain follow-up only.",
  answer:
    "History of present illness updated; no allergies documented. Plan: continue current regimen, " +
    "orthopedics referral for the knee. No new medications introduced this encounter.",
  confidence: "0.96",
  agreement: "3 / 3",
  pillar: "Safety",
  pillarStatus: "clear ✓",
  verdict: "PASS",
};

export default function VerdictCard({ data } = {}) {
  const d = { ...DEMO, ...(data || {}) };
  return (
    <div className="icard">
      <div className="icard-hd">
        <span className="ic"><Icon name="check" size={15} /></span>
        <span className="ttl">Sample verdict</span>
        <span className="sub">{d.id}</span>
        <span className="right"><span className="tag pass">{d.verdict}</span></span>
      </div>
      <div className="icard-bd">
        <div className="verdict">
          <div className="vmain">
            <div className="qline"><b>Q.</b> {d.question}</div>
            <div className="aline">{d.answer}</div>
          </div>
          <div className="vside">
            <div className="vstat"><div className="k">Confidence</div><div className="v big">{d.confidence}</div></div>
            <div className="vstat">
              <div className="k">Judge agreement</div>
              <div className="v">{d.agreement}</div>
              <div className="agree-dots"><i className="ad" /><i className="ad" /><i className="ad" /></div>
            </div>
            <div className="vstat"><div className="k">{d.pillar}</div><div className="v" style={{ color: "var(--teal)" }}>{d.pillarStatus}</div></div>
          </div>
        </div>
      </div>
    </div>
  );
}

registerTool("tool-verdict_card", VerdictCard);
