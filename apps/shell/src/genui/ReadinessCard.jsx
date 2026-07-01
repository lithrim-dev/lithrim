/* ReadinessCard.jsx — the inline "setup gaps" card (tool-readiness_card).

   The conversational-first surface for the agent↔pack readiness preflight (GET
   /v1/agents/{agent}/readiness). When a pack-declared fact-check can't run for the active agent —
   the silent hole where the council votes with the pack lens but ground() reads contracts from the
   agent ontology — the human sees WHY inline (never in the closed pane), with a one-click
   remediation. Real-data only: it renders the BFF ReadinessReport (flat-spread props); an ok report
   shows an honest "ready" state, never a fabricated all-clear. [[no-static-components-in-live-eval-ui]] */
import { Icon } from "../icons.jsx";
import { registerTool } from "./registry.js";

// check id -> a human label (the report's machine check name, humanized for the card header line).
const CHECK_LABEL = {
  CONTRACT_COVERAGE: "Missing fact-check",
  TOOL_REACHABILITY: "Tool unavailable",
  EXECUTOR_PRESENCE: "No executor",
  CONTRACT_FLAG_VALIDITY: "Dead fact-check",
  LENS_VS_CONTRACT_GAP: "Ungrounded flag",
  UNASSESSED: "Not assessed",
};
const checkLabel = (c) => CHECK_LABEL[c] || c;

// severity -> tone (chip class + color + the plain-word the human reads).
const sev = (s) =>
  String(s || "").toUpperCase() === "ERROR"
    ? { cls: "fail", color: "var(--accent)", word: "must fix" }
    : { cls: "warn", color: "var(--amber)", word: "warning" };

export default function ReadinessCard({
  ok, pack, agent, findings, onFix, onSwitchAgent,
} = {}) {
  // Real-data only: no report at all (an output-less mount) → an honest placeholder, never a
  // fabricated "fact-checks won't run". [[no-static-components-in-live-eval-ui]]
  const hasReport = ok !== undefined || Array.isArray(findings);
  const list = Array.isArray(findings) ? findings : [];
  const errors = list.filter((f) => String(f.severity || "").toUpperCase() === "ERROR");
  const ready = !!ok && errors.length === 0;
  const badge = !hasReport ? "—" : ready ? "Ready" : errors.length ? `${errors.length} to fix` : "Warnings";
  const badgeCls = !hasReport ? "warn" : ready ? "pass" : errors.length ? "fail" : "warn";
  return (
    <div className="icard" data-testid="readiness-card">
      <div className="icard-hd">
        <span className="ic" style={{ color: !hasReport ? "var(--muted)" : ready ? "var(--teal)" : "var(--accent)" }}>
          <Icon name={ready ? "check" : "flag"} size={15} />
        </span>
        <span className="ttl">Setup readiness</span>
        {pack && <span className="sub">{pack}{agent ? ` · ${agent}` : ""}</span>}
        <span className="right"><span className={"tag " + badgeCls}>{badge}</span></span>
      </div>
      <div className="icard-bd">
        {!hasReport ? (
          <div style={{ color: "var(--muted)", fontSize: 12.5, padding: "6px 2px" }}>
            No readiness check yet — pick an agent and pack to check the setup.
          </div>
        ) : ready ? (
          <div style={{ color: "var(--muted)", fontSize: 12.5, padding: "6px 2px" }}>
            This agent is ready to grade the {pack} pack — every declared fact-check can run.
          </div>
        ) : (
          <>
            <div style={{ fontSize: 12.5, color: "var(--fg)", lineHeight: 1.5, marginBottom: 8 }}>
              Some fact-checks won't run in this setup. A floor that can't fire fails <b>silently</b> —
              so a grade would look confident while a false alarm goes uncaught.
            </div>
            {list.map((f, i) => {
              const t = sev(f.severity);
              return (
                <div
                  key={(f.check || "") + (f.code || i)}
                  data-testid={`readiness-finding-${f.check}`}
                  className="ifloor"
                  style={{ margin: "8px 0", padding: "8px 10px", borderRadius: 8, background: t.cls === "fail" ? "var(--accent-bg, rgba(240,90,70,0.07))" : "var(--amber-bg, rgba(210,150,20,0.08))", borderLeft: `3px solid ${t.color}` }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4, flexWrap: "wrap" }}>
                    <span className={"tag " + t.cls}>{t.word}</span>
                    <span style={{ fontSize: 11, color: t.color, textTransform: "uppercase", letterSpacing: 0.3 }}>{checkLabel(f.check)}</span>
                    {f.code && <span style={{ fontSize: 11.5, color: "var(--muted)" }}>{f.code}</span>}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--fg)", lineHeight: 1.45 }}>{f.message}</div>
                  {f.remediation && (
                    <div style={{ fontSize: 11.5, color: "var(--muted)", lineHeight: 1.45, marginTop: 3 }}>{f.remediation}</div>
                  )}
                  {onFix && t.cls === "fail" && (
                    <button className="btn btn-ghost" data-testid={`readiness-fix-${f.check}`} style={{ marginTop: 7 }} onClick={() => onFix(f)}>
                      Add the fact-check <Icon name="chevR" size={13} />
                    </button>
                  )}
                </div>
              );
            })}
            {onSwitchAgent && (
              <button className="btn btn-ghost" data-testid="readiness-switch-agent" style={{ marginTop: 4 }} onClick={() => onSwitchAgent()}>
                Switch to a {pack || "pack"}-aligned agent
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

registerTool("tool-readiness_card", ReadinessCard);
