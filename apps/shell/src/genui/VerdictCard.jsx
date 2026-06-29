/* VerdictCard.jsx — datapoint component (tool-verdict_card, SPEC §5b).
   Renders a REAL council verdict only — no hardcoded sample (renderTool spreads
   part.output directly as props; an output-less mount renders an honest empty state,
   NOT a fabricated PASS). Color/icon are driven by the verdict so a REJECT reads
   negative (coral/fail) — mirrors artifact.jsx VERDICT_UI. [[no-static-components-in-live-eval-ui]] */
import { Icon } from "../icons.jsx";
import { registerTool } from "./registry.js";
import ClinicianVerdict from "./ClinicianVerdict.jsx";
import { verdictLabel, roleLabel, flagLabel } from "./copy.js";

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

// The named case outcome (independent-axes rule table) — the PRIMARY headline. The three
// reviewers are NOT aggregated into a score; this is the rule-table label over their verdicts.
const OUTCOME = {
  CRITICAL: { cls: "fail", icon: "flag", color: "var(--accent)", label: "Critical" },
  POLICY_VIOLATION: { cls: "fail", icon: "flag", color: "var(--accent)", label: "Policy violation" },
  RISK_FLAG: { cls: "warn", icon: "flag", color: "var(--amber)", label: "Risk flag" },
  FINDING: { cls: "warn", icon: "flag", color: "var(--amber)", label: "Finding" },
  NEEDS_REVIEW: { cls: "warn", icon: "flag", color: "var(--amber)", label: "Needs review" },
  CLEAR: { cls: "pass", icon: "check", color: "var(--teal)", label: "Clear" },
};

// a per-judge vote (PASS|WARN|FAIL|BLOCK) -> chip color (mirrors artifact.jsx VOTE_COLOR).
const VOTE_COLOR = { PASS: "var(--teal)", WARN: "var(--amber)", FAIL: "var(--accent)", BLOCK: "var(--accent)" };

// "1 / 3" -> [true, false, false]; falls back to three filled when unparseable.
function agreeDots(agreement) {
  const [num, den] = String(agreement || "").split("/").map((x) => parseInt(x.trim(), 10));
  if (!den || Number.isNaN(den)) return [true, true, true];
  return Array.from({ length: den }, (_, i) => i < (num || 0));
}

export default function VerdictCard({
  id, question, answer, confidence, agreement, pillar, pillarStatus, verdict,
  votes, floorBlocks, runId, onOpenArtifact, caseOutcome,
} = {}) {
  // Real-data only: with no outcome/verdict (and no question), this was an output-less mount —
  // show an honest placeholder instead of a fabricated sample verdict.
  if (!verdict && !question && !caseOutcome) {
    return (
      <div className="icard">
        <div className="icard-hd"><span className="ttl">Result</span></div>
        <div className="icard-bd">
          <div style={{ color: "var(--muted)", fontSize: 12.5, padding: "8px 2px" }}>
            No result yet — run an evaluation to see the reviewers' result here.
          </div>
        </div>
      </div>
    );
  }

  // The named case outcome is PRIMARY when present; else fall back to the PASS/WARN/BLOCK tone.
  const oc = caseOutcome ? OUTCOME[String(caseOutcome).toUpperCase()] : null;
  const t = oc || tone(verdict);
  const headline = oc ? oc.label : verdictLabel(verdict);
  return (
    <div className="icard">
      <div className="icard-hd">
        <span className="ic" style={{ color: t.color }}><Icon name={t.icon} size={15} /></span>
        <span className="ttl">Result</span>
        {id && <span className="sub">{id}</span>}
        <span className="right"><span className={"tag " + t.cls}>{headline}</span></span>
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
                <div className="k">Reviewer agreement</div>
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

        {/* INLINE-IMPACT-1 (the demo's thesis, inline): WHO caught the flip — a deterministic
            FLOOR rule the human authored, not a judge. Rendered only when a floor injected a block,
            so a clean pass never shows a fabricated attribution. */}
        {Array.isArray(floorBlocks) && floorBlocks.length > 0 && (
          <div className="ifloor" style={{ margin: "10px 0", padding: "8px 10px", borderRadius: 8, background: "var(--accent-bg, rgba(240,90,70,0.07))", borderLeft: "3px solid var(--accent)" }}>
            <div style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, color: "var(--accent)", marginBottom: 5 }}>Caught by a fact-check</div>
            {floorBlocks.map((b, i) => (
              <div key={b.flag || i} style={{ marginBottom: i < floorBlocks.length - 1 ? 6 : 0 }}>
                <span className="tag fail" style={{ marginRight: 6 }}>{flagLabel(b.flag)}</span>
                <span style={{ fontSize: 11.5, color: "var(--muted)" }}>
                  {b.contract_type}{b.contract ? ` · ${b.contract}` : ""}
                </span>
                {b.disposition && (
                  <div style={{ fontSize: 12, color: "var(--fg)", lineHeight: 1.45, marginTop: 3 }}>{b.disposition}</div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* CONV-FIRST §3: the realized per-judge votes, INLINE — the human reads how each
            judge voted in the conversation, not the pane. INLINE-IMPACT-1: each judge's REASON
            renders under the vote so the verdict reads as reasoned judgment, not a bare scorecard. */}
        {Array.isArray(votes) && votes.length > 0 && (
          <div className="ivotes">
            <div className="ivotes-h">How each reviewer voted</div>
            {votes.map((v, i) => {
              const c = VOTE_COLOR[String(v.vote || "").toUpperCase()] || "var(--muted)";
              const conf = typeof v.confidence === "number" ? v.confidence : null;
              return (
                <div key={v.role || i} style={{ marginBottom: v.reason ? 7 : 0 }}>
                  <div className="ivote">
                    <span className="ivote-av" style={{ background: c }}>{roleLabel(v.role).charAt(0).toUpperCase()}</span>
                    <span className="ivote-role">{roleLabel(v.role)}</span>
                    <span className="ivote-vote" style={{ color: c }}>{verdictLabel(v.vote)}</span>
                    {conf != null && <span className="ivote-conf">{conf.toFixed(2)}</span>}
                    {/* this axis's OWN sampling variance (independent — never averaged across reviewers). */}
                    {typeof v.variance === "number" && (
                      <span className="ivote-conf" title={`variance over k=${v.k ?? "?"} samples`} style={{ color: v.variance >= 0.2 ? "var(--amber)" : "var(--muted)" }}>
                        var {v.variance.toFixed(2)}{v.k ? ` · k=${v.k}` : ""}
                      </span>
                    )}
                  </div>
                  {v.reason && (
                    <div style={{ fontSize: 11.5, color: "var(--muted)", lineHeight: 1.45, margin: "1px 0 0 26px" }}>{v.reason}</div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* CONV-FIRST §3: the clinician-verdict (dissent) form, INLINE — the physician records
            their own pass/fail + names the judge's fallacy without leaving the conversation. */}
        {runId && <ClinicianVerdict runId={runId} councilVerdict={verdict} />}

        {/* the explicit drill-down: the ONLY inline affordance that opens the pane. */}
        {onOpenArtifact && (
          <button className="btn btn-ghost" style={{ marginTop: 10 }} onClick={() => onOpenArtifact("report")}>
            Open full report <Icon name="chevR" size={13} />
          </button>
        )}
      </div>
    </div>
  );
}

registerTool("tool-verdict_card", VerdictCard);
