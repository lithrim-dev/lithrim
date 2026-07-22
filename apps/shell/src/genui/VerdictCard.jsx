/* VerdictCard.jsx — datapoint component (tool-verdict_card, SPEC §5b).
   Renders a REAL council verdict only — no hardcoded sample (renderTool spreads
   part.output directly as props; an output-less mount renders an honest empty state,
   NOT a fabricated PASS). Color/icon are driven by the verdict so a REJECT reads
   negative (coral/fail) — mirrors artifact.jsx VERDICT_UI. [[no-static-components-in-live-eval-ui]] */
import { Icon } from "../icons.jsx";
import { registerTool } from "./registry.js";
import ClinicianVerdict from "./ClinicianVerdict.jsx";
import { reviewerLabel, verdictLabel, roleLabel, flagLabel, voteReason } from "./copy.js";
import { caseRead } from "./reportRead.js";

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
  FLAGGED: { cls: "fail", icon: "flag", color: "var(--accent)", label: "Flagged" },
  RISK_FLAG: { cls: "warn", icon: "flag", color: "var(--amber)", label: "Risk flag" },
  FINDING: { cls: "warn", icon: "flag", color: "var(--amber)", label: "Finding" },
  NEEDS_REVIEW: { cls: "warn", icon: "flag", color: "var(--amber)", label: "Needs review" },
  CLEAR: { cls: "pass", icon: "check", color: "var(--teal)", label: "Clear" },
};

// FLOOR-STORY-1: the shared flip-story line (verbatim the Report banner's copy) — the ONE
// reading of a floor-cleared run: reviewers flagged it, a fact-check cleared the findings.
const floorClearStory = (n, finalLabel) =>
  `Reviewers flagged it · a fact-check cleared ${n} false alarm${n === 1 ? "" : "s"} · final: ${finalLabel}`;

// a per-judge vote (PASS|WARN|FAIL|BLOCK) -> chip color (mirrors artifact.jsx VOTE_COLOR).
const VOTE_COLOR = { PASS: "var(--teal)", WARN: "var(--amber)", FAIL: "var(--accent)", BLOCK: "var(--accent)" };

// R2c: the per-sample verdict split from the raw decision scores (0.0 block / 0.5 review /
// 1.0 pass). "5×[0,0,1,1,1]" → "2B/3P" (review samples shown only when present). Null on
// no/one-sample data — a k=1 vote has no split to show.
export function sampleSplit(scoresRaw) {
  if (!Array.isArray(scoresRaw) || scoresRaw.length < 2) return null;
  let b = 0, w = 0, p = 0;
  for (const s of scoresRaw) {
    if (s <= 0.25) b += 1;
    else if (s >= 0.75) p += 1;
    else w += 1;
  }
  return [b ? `${b}B` : "", w ? `${w}R` : "", p ? `${p}P` : ""].filter(Boolean).join("/");
}

// "1 / 3" -> [true, false, false]; falls back to three filled when unparseable.
function agreeDots(agreement) {
  const [num, den] = String(agreement || "").split("/").map((x) => parseInt(x.trim(), 10));
  if (!den || Number.isNaN(den)) return [true, true, true];
  return Array.from({ length: den }, (_, i) => i < (num || 0));
}

export default function VerdictCard({
  id, question, answer, confidence, agreement, pillar, pillarStatus, verdict,
  votes, floorBlocks, floorClears, runId, onOpenArtifact, caseOutcome,
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
  // FLOOR-STORY-1: on a floor-cleared run (a passing verdict WITH fact-check clears) the pass IS
  // the result — a harsh pre-floor case_outcome (e.g. a pre-fix server's FLAGGED) never overrides
  // it into a contradicting headline; the flip renders as the story strip below instead.
  const flipStory = Array.isArray(floorClears) && floorClears.length > 0 && /^(approve|pass)$/i.test(String(verdict || ""));
  const oc = !flipStory && caseOutcome ? OUTCOME[String(caseOutcome).toUpperCase()] : null;
  const t = oc || tone(verdict);
  const headline = oc ? oc.label : verdictLabel(verdict);
  // NARRATIVE-LAYER-1: the plain-language read of THIS result (who wobbled, who held),
  // computed from the real votes + floor events — null (no band) when there is nothing to read.
  const read = caseRead({ votes, floorBlocks, floorClears, verdict });
  return (
    <div className="icard">
      <div className="icard-hd">
        <span className="ic" style={{ color: t.color }}><Icon name={t.icon} size={15} /></span>
        <span className="ttl">Result</span>
        {id && <span className="sub">{id}</span>}
        <span className="right"><span className={"tag " + t.cls}>{headline}</span></span>
      </div>
      <div className="icard-bd">
        {read && (
          <div data-testid="verdict-read" style={{ margin: "0 0 10px", padding: "8px 10px", borderRadius: 8, background: "var(--surface-muted, rgba(120,120,120,0.06))", borderLeft: "3px solid var(--border)" }}>
            <div style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, color: "var(--muted)", marginBottom: 5 }}>The read</div>
            <div style={{ fontSize: 12, color: "var(--fg)", lineHeight: 1.5 }}>{read}</div>
          </div>
        )}
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

        {/* FLOOR-CLEAR-1 (the SNOMED-flip thesis, inline): the symmetric attribution — a judge
            RAISED a finding that a deterministic fact-check then DISPROVED, so a flagged case still
            PASSES. Teal (positive): the false alarm + the rule's evidence. Rendered only when a floor
            actually suppressed something, so a real clean pass never shows a fabricated 'cleared'. */}
        {Array.isArray(floorClears) && floorClears.length > 0 && (
          <div className="ifloor" style={{ margin: "10px 0", padding: "8px 10px", borderRadius: 8, background: "var(--teal-bg, rgba(20,160,130,0.07))", borderLeft: "3px solid var(--teal)" }}>
            <div style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, color: "var(--teal)", marginBottom: 5 }}>Cleared by a fact-check</div>
            {/* FLOOR-STORY-1: the flip story (same copy as the Report banner) — only when the
                clears decided a passing final verdict, never a false "final: Passed" on a
                still-flagged partial clear. */}
            {flipStory && (
              <div style={{ fontSize: 11.5, color: "var(--muted)", marginBottom: 6 }}>
                {floorClearStory(floorClears.length, verdictLabel(verdict))}
              </div>
            )}
            {floorClears.map((c, i) => (
              <div key={c.flag || i} style={{ marginBottom: i < floorClears.length - 1 ? 6 : 0 }}>
                <span className="tag pass" style={{ marginRight: 6 }}>{flagLabel(c.flag)}</span>
                <span style={{ fontSize: 11.5, color: "var(--muted)" }}>false alarm disproven</span>
                {(c.evidence || c.reason) && (
                  <div style={{ fontSize: 12, color: "var(--fg)", lineHeight: 1.45, marginTop: 3 }}>{c.evidence || c.reason}</div>
                )}
                {/* REL-OPS-1 O2: the terminology release that decided this suppression — muted
                    secondary metadata; pre-O2 entries carry no field and render nothing. */}
                {c.terminology_edition && (
                  <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>terminology edition: {c.terminology_edition}</div>
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
              // R2c dual-confidence: the reviewer's own self-reported decision aggregate,
              // shown alongside the logprob confidence (never overwriting it). Null → no chip.
              const selfConf = typeof v.confidence_self === "number" ? v.confidence_self : null;
              const why = voteReason(v);
              const errs = Array.isArray(v.errors) ? v.errors.filter(Boolean) : [];
              return (
                <div key={v.role || i} style={{ marginBottom: why || errs.length ? 7 : 0 }}>
                  <div className="ivote">
                    <span className="ivote-av" style={{ background: c }}>{reviewerLabel(v).charAt(0).toUpperCase()}</span>
                    <span className="ivote-role">{roleLabel(v.role)}</span>
                    {/* a judge that ERRORED did not consider the case — never present its vote
                        (or its confidence numbers) as cast. */}
                    {errs.length > 0
                      ? <span className="tag fail">errored</span>
                      : <span className="ivote-vote" style={{ color: c }}>{verdictLabel(v.vote)}</span>}
                    {errs.length === 0 && conf != null && <span className="ivote-conf" title="calibrated confidence (from the model's logprobs)">{conf.toFixed(2)}</span>}
                    {/* R2c: the reviewer's own self-reported confidence, side-by-side with the
                        logprob number above — the two channels no longer collapse into one. */}
                    {errs.length === 0 && selfConf != null && (
                      <span className="ivote-conf" data-testid={`vote-selfconf-${v.role || i}`}
                        title="self-reported confidence (the reviewer's sampled decision aggregate)"
                        style={{ color: "var(--muted)" }}>
                        self {selfConf.toFixed(2)}
                      </span>
                    )}
                    {/* this axis's OWN sampling variance (independent — never averaged across
                        reviewers). k=1 has no spread, so "var 0.00 · k=1" was pure noise — hidden. */}
                    {typeof v.variance === "number" && v.k !== 1 && (
                      <span className="ivote-conf" title={`variance over k=${v.k ?? "?"} samples`} style={{ color: v.variance >= 0.2 ? "var(--amber)" : "var(--muted)" }}>
                        var {v.variance.toFixed(2)}{v.k ? ` · k=${v.k}` : ""}
                      </span>
                    )}
                    {/* R2c: the raw per-sample split — how the k completions actually voted. */}
                    {sampleSplit(v.scores_raw) && (
                      <span className="ivote-conf" data-testid={`vote-split-${v.role || i}`}
                        title="per-sample verdicts across the k completions"
                        style={{ color: "var(--muted)" }}>
                        {sampleSplit(v.scores_raw)}
                      </span>
                    )}
                    {/* F8: a single GRADED score (a reward model's 0.26 / 0.6 — not a 0|0.5|1
                        decision scalar) is the research-relevant number; surface it on the row. */}
                    {!sampleSplit(v.scores_raw) && Array.isArray(v.scores_raw) && v.scores_raw.length === 1 &&
                      typeof v.scores_raw[0] === "number" && ![0, 0.5, 1].includes(v.scores_raw[0]) && (
                      <span className="ivote-conf" data-testid={`vote-score-${v.role || i}`}
                        title="the reward model's raw graded score (low = unsafe; verdict = threshold at 0.5)"
                        style={{ color: "var(--muted)" }}>
                        score {v.scores_raw[0].toFixed(2)}
                      </span>
                    )}
                  </div>
                  {errs.length > 0 && (
                    <div style={{ fontSize: 11.5, color: "var(--accent)", lineHeight: 1.45, margin: "1px 0 0 26px" }}>{errs[0]}</div>
                  )}
                  {why && (
                    <div title={why} style={{ fontSize: 11.5, color: "var(--muted)", lineHeight: 1.45, margin: "1px 0 0 26px" }}>{why}</div>
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
