/* VerdictCard.jsx — datapoint component (tool-verdict_card, SPEC §5b).
   Renders a REAL council verdict only — no hardcoded sample (renderTool spreads
   part.output directly as props; an output-less mount renders an honest empty state,
   NOT a fabricated PASS). Color/icon are driven by the verdict so a REJECT reads
   negative (coral/fail) — mirrors artifact.jsx VERDICT_UI. [[no-static-components-in-live-eval-ui]] */
import { Icon } from "../icons.jsx";
import { registerTool } from "./registry.js";

// verdict -> tone (badge class + header icon + icon color). Accepts PASS/REJECT or
// approve/reject (and a few synonyms); unknown -> neutral warn.
const TONE = {
  approve: { cls: "pass", icon: "check", color: "var(--teal)" },
  pass: { cls: "pass", icon: "check", color: "var(--teal)" },
  reject: { cls: "fail", icon: "flag", color: "var(--accent)" },
  fail: { cls: "fail", icon: "flag", color: "var(--accent)" },
  block: { cls: "fail", icon: "flag", color: "var(--accent)" },
  needs_review: { cls: "warn", icon: "flag", color: "var(--amber)" },
  review: { cls: "warn", icon: "flag", color: "var(--amber)" },
};
const tone = (v) => TONE[String(v || "").toLowerCase().replace(/\s+/g, "_")] || TONE.needs_review;
const pillarColor = (s) => (/clear|pass|ok|✓/i.test(String(s || "")) ? "var(--teal)" : "var(--accent)");

// "1 / 3" -> [true, false, false]; falls back to three filled when unparseable.
function agreeDots(agreement) {
  const [num, den] = String(agreement || "").split("/").map((x) => parseInt(x.trim(), 10));
  if (!den || Number.isNaN(den)) return [true, true, true];
  return Array.from({ length: den }, (_, i) => i < (num || 0));
}

export default function VerdictCard({
  id, question, answer, confidence, agreement, pillar, pillarStatus, verdict,
} = {}) {
  // Real-data only: with no verdict (and no question), this was an output-less mount —
  // show an honest placeholder instead of a fabricated sample verdict.
  if (!verdict && !question) {
    return (
      <div className="icard">
        <div className="icard-hd"><span className="ttl">Verdict</span></div>
        <div className="icard-bd">
          <div style={{ color: "var(--muted)", fontSize: 12.5, padding: "8px 2px" }}>
            No verdict yet — run an eval to see the council's real verdict here.
          </div>
        </div>
      </div>
    );
  }

  const t = tone(verdict);
  return (
    <div className="icard">
      <div className="icard-hd">
        <span className="ic" style={{ color: t.color }}><Icon name={t.icon} size={15} /></span>
        <span className="ttl">Verdict</span>
        {id && <span className="sub">{id}</span>}
        <span className="right"><span className={"tag " + t.cls}>{verdict}</span></span>
      </div>
      <div className="icard-bd">
        <div className="verdict">
          <div className="vmain">
            {question && <div className="qline"><b>Q.</b> {question}</div>}
            {answer && <div className="aline">{answer}</div>}
          </div>
          <div className="vside">
            {confidence != null && (
              <div className="vstat"><div className="k">Confidence</div><div className="v big">{confidence}</div></div>
            )}
            {agreement != null && (
              <div className="vstat">
                <div className="k">Judge agreement</div>
                <div className="v">{agreement}</div>
                <div className="agree-dots">
                  {agreeDots(agreement).map((on, i) => <i key={i} className={on ? "ad" : "ad no"} />)}
                </div>
              </div>
            )}
            {pillar && (
              <div className="vstat"><div className="k">{pillar}</div><div className="v" style={{ color: pillarColor(pillarStatus) }}>{pillarStatus}</div></div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

registerTool("tool-verdict_card", VerdictCard);
