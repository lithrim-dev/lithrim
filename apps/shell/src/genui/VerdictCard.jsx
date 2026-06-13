/* VerdictCard.jsx — datapoint component (tool-verdict_card, SPEC §5b).
   Promoted from cards.jsx into the gen-UI registry. Kept visually faithful on the
   existing .icard chrome CSS (incremental adoption, SPEC §4 — the bespoke CSS is
   not rewritten into utilities); the foundation is exercised by the D2 input
   widgets.

   LOCKED datapoint prop convention (S-BS-19 / fresh-critic Ambiguity-2): a datapoint
   card destructures its fields DIRECTLY from props, which renderTool spreads from
   part.output ({...part.output}). NO {data} wrapper. Each field defaults to the demo
   value, so an output-less mount renders the demo. CalibrationChart already conforms
   (it spreads {points, ece, brier}); this card is conformed to match. */
import { Icon } from "../icons.jsx";
import { registerTool } from "./registry.js";

const DEMO = {
  id: "#1843 · dry run",
  question: "Does the reply stay within the published refund policy?",
  answer:
    "Approved the refund per the 30-day policy and linked the terms. No commitments " +
    "beyond what the policy allows; escalation path noted for edge cases.",
  confidence: "0.96",
  agreement: "3 / 3",
  pillar: "Faithfulness",
  pillarStatus: "clear ✓",
  verdict: "PASS",
};

export default function VerdictCard({
  id = DEMO.id,
  question = DEMO.question,
  answer = DEMO.answer,
  confidence = DEMO.confidence,
  agreement = DEMO.agreement,
  pillar = DEMO.pillar,
  pillarStatus = DEMO.pillarStatus,
  verdict = DEMO.verdict,
} = {}) {
  const d = { id, question, answer, confidence, agreement, pillar, pillarStatus, verdict };
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
