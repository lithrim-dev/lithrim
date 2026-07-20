/* artifact.jsx — right-hand inspectable surface with tabs + fullscreen.
   All four tabs render REAL BFF data (WS-5d wired them off the data.jsx mocks):
     - ReportTab  — runResult.composite (threaded via props; per-run)
     - JudgeTab   — runResult.council.votes (threaded via props; per-run realized votes)
     - ConfigTab  — GET /v1/ontology (self-fetched; the standing ontology config)
     - CorpusTab  — GET /v1/corpus (self-fetched; the correction flywheel) */
import { useEffect, useState } from "react";
import { Icon as ICN } from "./icons.jsx";
import { getOntology, getCorpus, getCase, listCaseBrowser, getRunAudit, getCaseReport } from "./bff.js";
import ClinicianVerdict from "./genui/ClinicianVerdict.jsx";
import { verdictLabel, roleLabel, flagLabel, friendlyError } from "./genui/copy.js";
import { caseRead, votesRead } from "./genui/reportRead.js";

// composite.verdict (reject|needs_review|approve) → banner chrome.
const VERDICT_UI = {
  approve: { icon: "check", label: "Passed", color: "var(--teal)" },
  needs_review: { icon: "flag", label: "Needs a look", color: "var(--amber)" },
  reject: { icon: "flag", label: "Flagged", color: "var(--accent)" },
};

// a reviewer vote (PASS|WARN|FAIL|BLOCK) → chip color.
const VOTE_COLOR = {
  PASS: "var(--teal)",
  WARN: "var(--amber)",
  FAIL: "var(--accent)",
  BLOCK: "var(--accent)",
};

// grade_path → the cost tag. in_process is the OSS-standalone PAID default (LAUNCH-PREP);
// only an actual replay is free — never label a paid run "free" (S-BS-110).
const gradeTag = (gp) =>
  gp === "replay" ? "Saved replay · free" : gp === "in_process" ? "Full run · paid" : "Live run · paid";

function ReportMessage({ children }) {
  return (
    <div style={{ padding: "48px 16px", textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
      {children}
    </div>
  );
}

// GRADE-GUARD-2: render a run failure. A "no captured baseline" failure is NOT a raw error to dump —
// it's actionable guidance: this eval has nothing to $0-replay yet, so grade it live ONCE to capture a
// baseline (then Run eval replays it for $0). Everything else renders the error through friendlyError
// (a calm sentence — never the raw HTTP verb/path/status/detail), and only hints "unreachable, restart
// it" for a genuine no-response/network failure.
// REPLAY-HONESTY-1: the server's replay refusals are two DIFFERENT states — a config-drift 409 (the
// baseline exists but the judges/checks/sampling changed since it was graded) and a true no-baseline —
// and both contain "run it live or in_process", so a single regex collapsed them into one generic card.
// The drift branch must come first and keep the case the server names; the no-baseline branch says when
// the real blocker is that no case is selected.
function RunFailed({ runError, activeCase = null }) {
  const errStr = String(runError || "");
  if (/config changed since/i.test(errStr)) {
    const caseId = (errStr.match(/case '([^']+)'/) || [])[1] || activeCase;
    return (
      <ReportMessage>
        <div style={{ color: "var(--accent)", fontWeight: 600, marginBottom: 6 }}>
          The setup changed since this case was last graded
        </div>
        <div style={{ marginTop: 4, lineHeight: 1.5 }}>
          {caseId ? (<>The saved baseline for <strong>{caseId}</strong> was</>) : (<>This case’s saved baseline was</>)}{" "}
          captured under an older setup — the judges, checks, or sampling have changed since, so replaying
          it would show a stale verdict. Use <strong>Run live</strong> to re-grade it once under the current
          setup; <strong>Run eval</strong> then replays the new baseline for $0.
        </div>
      </ReportMessage>
    );
  }
  if (/no captured baseline|\$0 replay is unavailable/i.test(errStr)) {
    return (
      <ReportMessage>
        <div style={{ color: "var(--accent)", fontWeight: 600, marginBottom: 6 }}>No saved run to replay yet</div>
        <div style={{ marginTop: 4, lineHeight: 1.5 }}>
          {activeCase ? (
            <>Case <strong>{activeCase}</strong> has no captured baseline, so the $0 replay (<strong>Run eval</strong>) has nothing to replay.</>
          ) : (
            <>No case is selected, so this run targeted the evaluation’s default case — which has no captured
            baseline for the $0 replay (<strong>Run eval</strong>) to use. Pick a case first: ask the assistant
            to open one, or choose one from the <strong>Cases</strong> tab.</>
          )}{" "}
          Use <strong>Run live</strong> to grade it once on your configured model — that captures a
          baseline, after which <strong>Run eval</strong> replays it for $0.
        </div>
      </ReportMessage>
    );
  }
  const isHttp = /→\s*\d{3}\b/.test(errStr);
  return (
    <ReportMessage>
      <div style={{ color: "var(--accent)", fontWeight: 600, marginBottom: 6 }}>We couldn't finish that run.</div>
      <div style={{ fontSize: 12.5 }}>{friendlyError(runError)}</div>
      {!isHttp && (
        <div style={{ marginTop: 10 }}>The evaluation service may be unreachable — ask the host to restart it.</div>
      )}
    </ReportMessage>
  );
}

// S-BS-168a: a plain-English "What this means" summary atop the Report — the verdict in
// words + WHY + the recommended action, composed from the (now-coherent, authored-aware)
// stage verdict and the per-reviewer votes. Confidence-HONEST (the no-manufactured-wins
// moat): a confident reject reads as a confirmed flag; a low-confidence needs-review reads
// as an uncertain point a person should check — the two are never flattened into one list.
// FLOOR-STORY-1: the shared flip-story line — the ONE reading of a floor-cleared run
// (reviewers flagged it, a deterministic fact-check cleared the findings, final verdict
// stands). Rendered verbatim on BOTH surfaces (Report banner + inline VerdictCard).
export function floorClearStory(n, finalLabel) {
  return `Reviewers flagged it · a fact-check cleared ${n} false alarm${n === 1 ? "" : "s"} · final: ${finalLabel}`;
}

function ReportSummary({ comp, votes }) {
  const verdict = String(comp.stage_verdict || "").toUpperCase();
  const isFlag = (v) => v.vote === "BLOCK" || v.vote === "FAIL" || /reject/i.test(String(v.vote || ""));
  const isUnsure = (v) => v.vote === "WARN" || /needs|review/i.test(String(v.vote || ""));
  const conf = (v) => (typeof v.confidence === "number" ? v.confidence : null);
  const name = (v) => roleLabel(v.judge_role || v.role);

  const flagged = votes.filter(isFlag);
  const unsure = votes.filter(isUnsure);
  const flaggedHighConf = flagged.length > 0 && flagged.every((v) => conf(v) !== null && conf(v) >= 0.5);
  const unsureLowConf = unsure.some((v) => conf(v) !== null && conf(v) < 0.5);
  // FLOOR-STORY-1: the floor cleared the reviewers' findings — the pass IS the result and the
  // flip is said explicitly; the layers are never concatenated into a contradiction.
  const cleared = (comp.grounded_adjustments || []).length;
  const floorCleared = verdict === "PASS" && flagged.length > 0 && cleared > 0;

  let parts;
  if (floorCleared) {
    parts = [
      "This case passed.",
      `The ${flagged.map(name).join(" and ")} flagged it; the fact-check layer cleared ${cleared === 1 ? "that finding as a false alarm" : "those findings as false alarms"}.`,
      "Final: passed.",
    ];
  } else {
    parts = [
      verdict === "BLOCK" ? "This case was flagged." : verdict === "PASS" ? "This case passed." : "This case needs a closer look.",
    ];
    if (flagged.length)
      parts.push(`The ${flagged.map(name).join(" and ")} flagged it${flaggedHighConf ? " with high confidence" : ""}.`);
    if (unsure.length)
      parts.push(`The ${unsure.map(name).join(" and ")} ${unsure.length > 1 ? "were" : "was"} uncertain${unsureLowConf ? " (low confidence)" : ""} — a person should take a look.`);
    // vote-less older runs: name the reason off the findings so the summary still says WHY.
    if (!flagged.length && !unsure.length && verdict !== "PASS" && (comp.active_findings || []).length)
      parts.push(`Issues raised: ${comp.active_findings.map(flagLabel).join(", ")}.`);
    if (verdict === "PASS")
      // "No reviewer raised an issue." only when that is TRUE — never beside a "flagged it".
      parts.push(flagged.length || unsure.length ? "A person should double-check the reviewer notes above." : "No reviewer raised an issue.");
    else parts.push("Recommend a person review this before it is relied on.");
  }

  // NARRATIVE-LAYER-1: the computed read of this case (who wobbled, who held) — the ONLY
  // narrative that covers a floor ENFORCEMENT; only floor_block rows count (inconclusive rows
  // are surfaced-never-flipped). Null -> no band; the summary below is unchanged either way.
  const read = caseRead({
    votes,
    floorBlocks: (comp.floor_adjustments || []).filter((a) => a.action === "floor_block"),
    floorClears: comp.grounded_adjustments || [],
    verdict: comp.stage_verdict,
  });

  return (
    <div className="art-sec" data-testid="report-summary">
      <div className="art-h2">What this means</div>
      {read && (
        <div data-testid="report-read" style={{ margin: "0 0 8px", padding: "8px 10px", borderRadius: 8, background: "var(--surface-muted, rgba(120,120,120,0.06))", borderLeft: "3px solid var(--border)" }}>
          <div style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, color: "var(--muted)", marginBottom: 5 }}>The read</div>
          <div style={{ fontSize: 12.5, color: "var(--text)", lineHeight: 1.5 }}>{read}</div>
        </div>
      )}
      <div style={{ fontSize: 13, lineHeight: 1.5, color: "var(--text)" }}>{parts.join(" ")}</div>
    </div>
  );
}

function ReportTab({ runStatus, runResult, runError, activeCase = null, agent = "ws0_default" }) {
  // REPORT-HYDRATE-1: an ARMED case with no in-session run hydrates the LATEST persisted
  // report for it (GET /v1/reports/{case_id}, a pure $0 read) and feeds the SAME renderer
  // below — never a parallel view. In-session state always wins (loading/error/fresh result);
  // a 404 (no saved run) keeps the honest empty state.
  const [hydrated, setHydrated] = useState(null);
  useEffect(() => {
    if (runResult || runStatus !== "idle" || !activeCase) { setHydrated(null); return; }
    let live = true;
    getCaseReport(agent, activeCase)
      .then((r) => { if (live) setHydrated(r); })
      .catch(() => { if (live) setHydrated(null); }); // no saved run / offline → empty state
    return () => { live = false; };
  }, [agent, activeCase, runResult, runStatus]);

  if (runStatus === "loading")
    return <ReportMessage>Running the evaluation…</ReportMessage>;
  if (runStatus === "error") return <RunFailed runError={runError} activeCase={activeCase} />;
  const shown = runResult || hydrated;
  if (!shown)
    return (
      <ReportMessage>
        No evaluation yet. Run one to see the verdict and report here.
      </ReportMessage>
    );

  const comp = shown.composite;
  // hardened: a record with no calibration fold renders the honest unlabeled branch, not a crash.
  const cal = shown.calibration_check || { label_status: "unlabeled", n_cases: 0 };
  const ui = VERDICT_UI[comp.verdict] || VERDICT_UI.needs_review;
  const gradeLabel = gradeTag(shown.grade_path);
  // The named case outcome (independent-axes rule table) — PRIMARY when present. Humanize
  // CRITICAL/POLICY_VIOLATION/… for the headline; the PASS/WARN/BLOCK grade stays on the right.
  const caseOutcome = (shown.council || {}).case_outcome || comp.case_outcome || null;
  const outcomeLabel = caseOutcome
    ? String(caseOutcome).replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase())
    : null;
  // FLOOR-STORY-1: the grounding floor cleared the reviewers' findings (votes flagged, final
  // PASS, clears present) — the flip renders as the product's story, never a contradicting
  // chip (a "Flagged" title over a "Passed" grade). A pre-fix server may still serve a harsh
  // pre-floor case_outcome; anything but CLEAR is overridden by the post-floor reading.
  const clears = comp.grounded_adjustments || [];
  const findings = comp.active_findings || []; // hardened: a partial/legacy composite must not crash the banner
  const votedFlag = ((shown.council || {}).votes || []).some((v) => ["BLOCK", "FAIL"].includes(String(v.vote || "").toUpperCase()));
  const floorCleared = clears.length > 0 && votedFlag && String(comp.stage_verdict || "").toUpperCase() === "PASS";
  const bannerTitle = floorCleared && String(caseOutcome || "").toUpperCase() !== "CLEAR" ? ui.label : (outcomeLabel || ui.label);

  return (
    <div>
      <div className="report-banner">
        <div className="rb-ic" style={{ color: ui.color }}><ICN name={ui.icon} size={20} sw={2.2} /></div>
        <div style={{ minWidth: 0 }}>
          <div className="rb-t">{bannerTitle}</div>
          <div className="rb-s">
            {findings.length} issues found · {clears.length} false alarms cleared by a fact-check · {shown.case_id}
          </div>
          {floorCleared && (
            <div className="rb-s" style={{ marginTop: 2, color: "var(--teal)" }}>
              {floorClearStory(clears.length, verdictLabel(comp.stage_verdict))}
            </div>
          )}
        </div>
        <div className="rb-grade" style={{ color: ui.color }}>{verdictLabel(comp.stage_verdict)}</div>
      </div>

      <ReportSummary comp={comp} votes={(shown.council || {}).votes || []} />

      <div className="art-sec">
        <div className="art-h2">
          Headline metrics
          <span className="cnt">{gradeLabel}</span>
        </div>
        <div className="tiles">
          {[
            { k: "Risk score", v: String(comp.score), d: "0–1 · higher is riskier" },
            { k: "Issues found", v: String(findings.length), d: "after fact-checks" },
            { k: "False alarms cleared", v: String(clears.length), d: "cleared by a fact-check" },
          ].map((t) => (
            <div className="tile" key={t.k}>
              <div className="tk">{t.k}</div>
              <div className="tv" style={{ fontSize: 18 }}>{t.v}</div>
              <div className="td">{t.d}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="art-sec">
        <div className="art-h2">
          Issues found <span className="cnt">{findings.length}</span>
        </div>
        {findings.length === 0 && (
          <div style={{ fontSize: 12.5, color: "var(--muted)" }}>None.</div>
        )}
        {findings.map((f, i) => (
          <div key={i} style={{ display: "flex", gap: 8, padding: "8px 0", borderBottom: "1px solid var(--border)", fontSize: 12.5 }}>
            <ICN name="flag" size={14} style={{ color: "var(--accent)", flex: "0 0 auto", marginTop: 2 }} />
            <span>{flagLabel(f)}</span>
          </div>
        ))}
      </div>

      {(comp.floor_adjustments || []).length > 0 && (
        <div className="art-sec">
          {/* FLOOR-STORY-1 honesty: "changed the result" ONLY when a floor_block row exists —
              floor_inconclusive rows are surfaced-never-flipped (grounding.py) and must not
              claim a flip. The per-row labels below were already honest. */}
          <div className="art-h2">
            {(comp.floor_adjustments || []).some((a) => a.action === "floor_block")
              ? (<>Automated fact-check failures <span className="cnt">a fact-check changed the result</span></>)
              : (<>Automated fact-checks <span className="cnt">fact-checks ran (inconclusive)</span></>)}
          </div>
          {(comp.floor_adjustments || []).map((a, i) => {
            const isBlock = a.action === "floor_block";
            return (
              <div key={i} style={{ padding: "8px 0", borderBottom: "1px solid var(--border)", fontSize: 12.5 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                  <span style={{ fontWeight: 600, color: isBlock ? "var(--accent)" : "var(--muted)" }}>{flagLabel(a.flag)}</span>
                  <span style={{ color: isBlock ? "var(--accent)" : "var(--muted)", whiteSpace: "nowrap" }}>
                    {isBlock ? "Blocked by a fact-check" : "Fact-check inconclusive"} · {a.contract_type}
                  </span>
                </div>
                <div style={{ color: "var(--muted)", marginTop: 3 }}>
                  conforms: {String(a.conforms)} · {a.disposition}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {clears.length > 0 && (
        <div className="art-sec">
          <div className="art-h2">Cleared by a fact-check <span className="cnt">fact-checked</span></div>
          {clears.map((a, i) => (
            <div key={i} style={{ padding: "8px 0", borderBottom: "1px solid var(--border)", fontSize: 12.5 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                <span style={{ fontWeight: 600 }}>{flagLabel(a.flag)}</span>
                <span style={{ color: "var(--teal)", whiteSpace: "nowrap" }}>{a.action} · {a.contract}</span>
              </div>
              {a.reason && <div style={{ color: "var(--muted)", marginTop: 3 }}>{a.reason}</div>}
              {/* REL-OPS-1 O2: the terminology release that decided this clear — absent on pre-O2 entries. */}
              {a.terminology_edition && <div style={{ color: "var(--muted)", marginTop: 2, fontSize: 11.5 }}>terminology edition: {a.terminology_edition}</div>}
            </div>
          ))}
        </div>
      )}

      <div className="art-sec" style={{ marginBottom: 4 }}>
        <div className="art-h2">Calibration <span className="cnt">N={cal.n_cases}</span></div>
        {cal.label_status === "unlabeled" ? (
          // HONEST-1: no ground truth -> withhold accuracy/ECE; never fabricate a 0.0/WARN.
          <div style={{ fontSize: 12.5, color: "var(--muted)", display: "flex", flexDirection: "column", gap: 6 }}>
            <div>No answer key for this case — the verdict is shown, but accuracy can’t be measured yet.</div>
            <div>Add the correct answer for this case to measure accuracy &amp; calibration.</div>
            {cal.caveat && <div style={{ fontSize: 11.5 }}>{cal.caveat}</div>}
          </div>
        ) : (
          <div style={{ fontSize: 12.5, display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>Verdict match</span>
              <span style={{ fontFamily: "var(--mono)", fontWeight: 600 }}>{cal.verdict_match_rate} · {cal.status}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>ECE</span>
              <span style={{ fontFamily: "var(--mono)" }}>{cal.ece}</span>
            </div>
            {cal.caveat && <div style={{ color: "var(--muted)", fontSize: 11.5 }}>{cal.caveat}</div>}
            <div style={{ color: "var(--muted)", fontSize: 11.5 }}>
              Shown for insight only — it doesn’t change the verdict.
            </div>
          </div>
        )}
      </div>

      <ClinicianVerdict runId={shown.pipeline_run_id} councilVerdict={comp.verdict} />
    </div>
  );
}

// The realized per-judge votes the council cast on THIS case (run-eval `council`).
// Per-case truth (what each judge voted + its confidence), not a configured roster.
function JudgeTab({ runStatus, runResult, runError }) {
  // TRANSPARENCY-1 (the Clinical Scribe Review contrast): each judge's LENS — the flags it COULD raise +
  // whether it did — lives in the run's provenance audit (GET /v1/runs/{id}/audit `withstands`),
  // NOT the grade-time council view. Self-fetch it (the ConfigTab/CorpusTab pattern) and key by
  // role, so a PASS that happened because NOTHING in the lens covers the defect (Risk-Severity
  // Blindness) is VISIBLE, not inferred.
  const runId = runResult?.pipeline_run_id;
  const [lensByRole, setLensByRole] = useState({});
  useEffect(() => {
    if (!runId) { setLensByRole({}); return; }
    let live = true;
    getRunAudit(runId)
      .then((a) => {
        if (!live) return;
        const map = {};
        for (const w of a.withstands || []) {
          const role = w.role || w.judge_role;
          const rules = (w.signals_weighed || {}).ontology_rules || [];
          map[role] = rules
            .filter((r) => r.in_lens)
            .map((r) => ({ code: r.code, raised: !!r.raised }));
        }
        setLensByRole(map);
      })
      .catch(() => { if (live) setLensByRole({}); }); // offline-safe: no lens, never a crash
    return () => { live = false; };
  }, [runId]);

  if (runStatus === "loading")
    return <ReportMessage>Gathering the reviewers' results…</ReportMessage>;
  if (runStatus === "error") return <RunFailed runError={runError} />;
  if (!runResult)
    return (
      <ReportMessage>
        No run yet. Press <strong>Run eval</strong> to see how each reviewer voted on this case.
      </ReportMessage>
    );

  const council = runResult.council || { votes: [], configured: [] };
  const votes = council.votes || [];
  if (votes.length === 0)
    return <ReportMessage>This run carried no per-reviewer votes.</ReportMessage>;

  const blocking = votes.filter((v) => v.vote === "FAIL" || v.vote === "BLOCK").length;
  // NARRATIVE-LAYER-1: the reviewer-spread read in words, computed from the realized votes;
  // the footnote fires only when a vote genuinely carries no (logprob) confidence.
  const read = votesRead(votes);
  // TRANSPARENCY-1: cohort lens coverage — how many distinct flags the whole council COULD raise
  // on this case, and how many it actually did. A big "could-flag" count next to "raised 0" is the
  // blind spot, quantified (Risk-Severity Blindness: it had lenses, none covered the defect).
  const lensCodes = new Set();
  let raisedCount = 0;
  votes.forEach((v) => (lensByRole[v.judge_role] || []).forEach((c) => { lensCodes.add(c.code); if (c.raised) raisedCount += 1; }));
  return (
    <div>
      {read && (
        <div data-testid="judges-read" style={{ margin: "0 0 14px", padding: "8px 10px", borderRadius: 8, background: "var(--surface-muted, rgba(120,120,120,0.06))", borderLeft: "3px solid var(--border)" }}>
          <div style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.4, color: "var(--muted)", marginBottom: 5 }}>The read</div>
          <div style={{ fontSize: 12.5, color: "var(--text)", lineHeight: 1.5 }}>{read.text}</div>
          {read.confidenceNote && (
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>confidence reads n/a where the model doesn't expose token logprobs</div>
          )}
        </div>
      )}
      <div className="consensus" style={{ marginBottom: 18 }}>
        <div className="big">{votes.length}</div>
        <div>
          <div className="ct">{blocking ? `${blocking} blocking vote(s)` : "No blocking votes"}</div>
          <div className="cs">
            How each reviewer voted on {runResult.case_id} · {gradeTag(runResult.grade_path)}
          </div>
          {lensCodes.size > 0 && (
            <div className="cs" style={{ marginTop: 2 }}>
              The reviewers could flag <strong>{lensCodes.size}</strong> issue type(s) on this case ·{" "}
              <strong style={{ color: raisedCount ? "var(--accent)" : "var(--muted)" }}>raised {raisedCount}</strong>
            </div>
          )}
        </div>
      </div>
      <div className="art-h2">Reviewers <span className="cnt">vote · what it checks for</span></div>
      {votes.map((v, i) => {
        const color = VOTE_COLOR[v.vote] || "var(--muted)";
        const conf = typeof v.confidence === "number" ? v.confidence : null;
        const lens = lensByRole[v.judge_role] || [];
        const raised = lens.filter((c) => c.raised);
        return (
          <div className="judge" key={v.judge_role || i}>
            <div className="judge-top">
              <div className="judge-av" style={{ background: color }}>
                {(v.judge_role || "?").charAt(0).toUpperCase()}
              </div>
              <div style={{ minWidth: 0 }}>
                <div className="judge-name">{roleLabel(v.judge_role)}</div>
                <div className="judge-model">{v.model || "—"}</div>
              </div>
              <div className="judge-w">
                <div className="k">vote</div>
                <div className="v" style={{ color }}>{verdictLabel(v.vote)}</div>
              </div>
            </div>
            <div className="vbar">
              <i style={{ width: (conf == null ? 0 : conf * 100) + "%", background: color }} />
            </div>
            <div className="vbar-leg">
              <span>
                <span className="d" style={{ background: color }} /> confidence{" "}
                {conf == null ? "n/a" : conf.toFixed(2)}
              </span>
              {/* this reviewer's OWN sampling variance over k samples (independent axis; never
                  averaged). k=1 has no spread — "variance 0.00 · k=1" was noise, so it's hidden. */}
              {typeof v.variance === "number" && v.k !== 1 && (
                <span style={{ color: v.variance >= 0.2 ? "var(--amber)" : "var(--muted)" }}>
                  variance {v.variance.toFixed(2)}{v.k ? ` · k=${v.k}` : ""}
                </span>
              )}
              {/* F8: a single GRADED score (a reward model's 0.26/0.6 — never a 0|0.5|1 decision
                  scalar) is the research-relevant number — same rule as the inline VerdictCard. */}
              {Array.isArray(v.scores_raw) && v.scores_raw.length === 1 && typeof v.scores_raw[0] === "number" &&
                ![0, 0.5, 1].includes(v.scores_raw[0]) && (
                <span data-testid={`judge-score-${v.judge_role || v.role}`}
                  title="the reward model's raw graded score (low = unsafe; verdict = threshold at 0.5)">
                  score {v.scores_raw[0].toFixed(2)}
                </span>
              )}
              {v.reason && <span style={{ color: "var(--muted)" }}>{v.reason.slice(0, 80)}{v.reason.length > 80 ? "…" : ""}</span>}
            </div>
            {lens.length > 0 && (
              <div className="judge-lens">
                <span className="jl-k">Checks for</span>
                {lens.map((c) => (
                  <span key={c.code} className={"jl-code" + (c.raised ? " raised" : "")}>{flagLabel(c.code)}</span>
                ))}
                <span className="jl-note" style={{ color: raised.length ? "var(--accent)" : "var(--muted)" }}>
                  {raised.length ? `raised ${raised.map((c) => flagLabel(c.code)).join(", ")}` : "raised none"}
                </span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// The standing ontology config, read from GET /v1/ontology (the §3 "ontology config
// editor" view, read-only here — edits go through the FlagEditor/PUT path, not a
// textarea). Self-fetches because the ontology is run-independent.
function ConfigTab({ agent = "ws0_default", wsPack = null }) {
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [ont, setOnt] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let live = true;
    setStatus("loading");
    getOntology(agent)
      .then((o) => { if (live) { setOnt(o); setStatus("ready"); } })
      .catch((e) => { if (live) { setError(String(e.message || e)); setStatus("error"); } });
    return () => { live = false; };
  }, [agent]);

  if (status === "loading") return <ReportMessage>Loading setup…</ReportMessage>;
  if (status === "error")
    return (
      <ReportMessage>
        <div style={{ color: "var(--accent)", fontWeight: 600, marginBottom: 6 }}>We couldn’t load the setup. Please try again.</div>
      </ReportMessage>
    );

  const sm = ont.severity_map || {};
  const flags = ont.flags || [];
  const contracts = ont.verification_contracts || [];
  const gradeable = flags.filter((f) => f.gradeable).length;

  // F3: before this workspace has a configured evaluation, GET /v1/ontology resolves the
  // leaked `_core` seed sample — so a non-`_core` workspace would mislabel its Setup as
  // "generic · _core/1". Suppress that stale domain·version chip until a real ontology for
  // this workspace's pack is resolved (the chip returns once the user creates an evaluation).
  const labelMismatch = wsPack && wsPack !== "_core" && ont.ontology_version === "_core/1";

  return (
    <div>
      <div className="art-sec">
        <div className="art-h2">
          What the reviewers check {labelMismatch
            ? <span className="cnt" data-testid="config-domain-pending">setting up…</span>
            : <span className="cnt">{ont.domain} · {ont.ontology_version}</span>}
        </div>
        <div className="tiles">
          {[
            { k: "Checks", v: String(flags.length), d: `${gradeable} scored` },
            { k: "Fact-checks", v: String(contracts.length), d: "automated rules" },
            { k: "Block at", v: String(sm.block_at_or_above ?? "—"), d: "risk threshold" },
            { k: "Warn above", v: String(sm.warn_above ?? "—"), d: "risk threshold" },
          ].map((t) => (
            <div className="tile" key={t.k}>
              <div className="tk">{t.k}</div>
              <div className="tv" style={{ fontSize: 18 }}>{t.v}</div>
              <div className="td">{t.d}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="art-sec">
        <div className="art-h2">Severity weights <span className="cnt">global</span></div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {Object.entries(sm.weights || {}).map(([k, v]) => (
            <span key={k} className="cnt" style={{ fontFamily: "var(--mono)" }}>{k} {v}</span>
          ))}
        </div>
      </div>

      <div className="art-sec">
        <div className="art-h2">
          Checks <span className="cnt">level · scored · reviewers</span>
        </div>
        {flags.map((f) => (
          <div key={f.flag} style={{ display: "flex", gap: 8, alignItems: "baseline", padding: "7px 0", borderBottom: "1px solid var(--border)", fontSize: 12 }}>
            <span style={{ fontWeight: 600, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }}>{flagLabel(f.flag)}</span>
            <span className="cnt">{f.tier || "—"}</span>
            <span style={{ color: f.gradeable ? "var(--teal)" : "var(--muted)" }}>{f.gradeable ? "scored" : "reference"}</span>
            <span style={{ color: "var(--muted)", fontSize: 11 }}>{(f.owner_roles || []).length || "no"} reviewer(s)</span>
          </div>
        ))}
      </div>

      {contracts.length > 0 && (
        <div className="art-sec" style={{ marginBottom: 4 }}>
          <div className="art-h2">Fact-checks <span className="cnt">automated rules</span></div>
          {contracts.map((c, i) => (
            <div key={i} style={{ padding: "7px 0", borderBottom: "1px solid var(--border)", fontSize: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                <span style={{ fontWeight: 600 }}>{flagLabel(c.flag_code)}</span>
                <span style={{ color: "var(--teal)", whiteSpace: "nowrap" }}>{c.contract_type} · {c.version}</span>
              </div>
              {c.question && <div style={{ color: "var(--muted)", marginTop: 3 }}>{c.question}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// CASE-BROWSER-1 (UI-pass 2026-07-04 finding #1): the case-DISCOVERY surface — GET
// /v1/cases/browser lists every case the grade can load for this agent (pinned source +
// pack fixtures + ingested, the exact load_case resolution order), each row carrying the
// by-construction label, this agent's run count, and the baseline-freshness dot ("would
// the $0 replay serve?" — computed server-side with the SAME assembly the grade hashes).
// Clicking a row SELECTS the case for the Run buttons (the same activeCase state the
// assistant's open-case tool sets — the displayed case IS the armed case). Self-fetched
// so it survives a reload, independent of any chat session (supersedes the NARR-LOOP
// ingested-only list, which hid pack/pinned cases and showed nothing on a fresh clone).
const _BASELINE_DOT = {
  fresh: { color: "var(--teal)", title: "baseline: fresh — Run eval replays it for $0" },
  stale: { color: "var(--amber)", title: "baseline: stale — the setup changed since; re-grade live once" },
  none: { color: "var(--muted)", title: "no saved baseline — grade it live once, then Run eval replays for $0" },
  unknown: { color: "var(--muted)", title: "baseline: unknown" },
};

// COHORT-SUBSET-1 (feat/cohort-and-subset-ui): the browser also multi-SELECTS a cohort. A per-row
// checkbox toggles membership in the lifted `selectedIds` Set (App-owned, so panes/palette read it);
// the row BODY click still ARMS a single case (unchanged default — empty set = today's behavior).
// "Run selected (N)" (hidden on an empty set) fires the SAME cohort cost-confirm the chat's
// propose_run_all opens, via the `lithrim:grade-cohort` window bridge carrying the selected case_ids
// (the subset-capable gradeCases param). The pane never spends — the confirm is the only paid path.
function CaseBrowserSection({ agent = "ws0_default", activeCase = null, onSelectCase, selectedIds = null, onToggleSelect }) {
  const [browse, setBrowse] = useState(null);
  const [status, setStatus] = useState("loading");
  useEffect(() => {
    let live = true;
    listCaseBrowser(agent)
      .then((b) => { if (live) { setBrowse(b); setStatus("ready"); } })
      .catch(() => { if (live) setStatus("ready"); }); // offline-safe: empty-state, never a crash
    return () => { live = false; };
  }, [agent]);
  if (status !== "ready") return null;
  const sel = selectedIds || new Set();
  const multi = typeof onToggleSelect === "function"; // the checkbox column only when the App wired selection
  const runSelected = () => { try { window.dispatchEvent(new CustomEvent("lithrim:grade-cohort", { detail: { case_ids: [...sel] } })); } catch {} };
  const cases = (browse || {}).cases || [];
  if (cases.length === 0)
    return (
      <div className="art-sec">
        <div className="art-h2">Cases <span className="cnt">what the evaluation can grade</span></div>
        <div style={{ color: "var(--muted)", fontSize: 12.5 }}>
          No cases to browse yet — load cases from a JSON, JSONL, or CSV file (the 📎 in the
          chat composer), or ask the assistant to load a sample.
        </div>
      </div>
    );
  return (
    <div className="art-sec">
      <div className="art-h2" style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span style={{ flex: 1, minWidth: 0 }}>
          Cases <span className="cnt">{cases.length}{browse.truncated ? "+ (truncated)" : ""} · click one to select it for the Run buttons{multi ? "; check to grade several" : ""}</span>
        </span>
        {multi && sel.size > 0 && (
          <button className="btn btn-primary" data-testid="run-selected" title="Grade the checked cases (opens the paid cost-confirm)"
            style={{ flexShrink: 0, fontSize: 12, padding: "3px 10px" }} onClick={runSelected}>
            Run selected ({sel.size})
          </button>
        )}
      </div>
      {cases.map((c) => {
        const active = c.case_id === activeCase;
        const checked = sel.has(c.case_id);
        const dot = _BASELINE_DOT[c.baseline] || _BASELINE_DOT.unknown;
        return (
          <div key={c.case_id} onClick={() => onSelectCase?.(c.case_id)}
            style={{ padding: "8px 6px", margin: "0 -6px", borderBottom: "1px solid var(--border)", fontSize: 12, display: "flex", gap: 8, alignItems: "baseline", cursor: onSelectCase ? "pointer" : "default", borderRadius: 6, background: active ? "var(--surface-2, rgba(127,127,127,0.10))" : "transparent" }}>
            {multi && (
              <input type="checkbox" data-testid={`case-check-${c.case_id}`} checked={checked}
                onClick={(e) => e.stopPropagation()} onChange={() => onToggleSelect(c.case_id)}
                title="Add this case to the cohort to grade" style={{ flexShrink: 0, cursor: "pointer", alignSelf: "center" }} />
            )}
            <span title={dot.title} style={{ color: dot.color, flexShrink: 0 }}>●</span>
            <span style={{ fontFamily: "var(--mono)", fontWeight: active ? 600 : 400, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }}>{c.case_id}</span>
            {c.labeled ? (
              c.defect ? (
                <span className="cnt" style={{ color: "var(--accent)", whiteSpace: "nowrap" }}>{flagLabel(c.defect)}</span>
              ) : (
                <span className="cnt" style={{ color: "var(--teal)" }}>clean</span>
              )
            ) : (
              <span className="cnt">unlabeled</span>
            )}
            <span className="cnt" style={{ whiteSpace: "nowrap" }}>{c.runs} run{c.runs === 1 ? "" : "s"}</span>
          </div>
        );
      })}
    </div>
  );
}

// The Cases tab = the browsable case list (above) + the correction flywheel (below).
function CorpusTab({ agent = "ws0_default", activeCase = null, onSelectCase, selectedIds = null, onToggleSelect }) {
  return (
    <div>
      <CaseBrowserSection agent={agent} activeCase={activeCase} onSelectCase={onSelectCase} selectedIds={selectedIds} onToggleSelect={onToggleSelect} />
      <CorrectionCorpus />
    </div>
  );
}

// The correction-corpus / flywheel view — GET /v1/corpus (corpus-row/1). Each row is
// a logged grounding correction (suppress | floor) with before→after verdict + the
// contract + owner roles + a rollout pointer. The corpus may be empty until a
// run writes corrections — empty-state, never a crash.
function CorrectionCorpus() {
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let live = true;
    setStatus("loading");
    getCorpus()
      .then((body) => { if (live) { setRows(body.rows || []); setStatus("ready"); } })
      .catch((e) => { if (live) { setError(String(e.message || e)); setStatus("error"); } });
    return () => { live = false; };
  }, []);

  if (status === "loading") return <ReportMessage>Loading saved cases…</ReportMessage>;
  if (status === "error")
    return (
      <ReportMessage>
        <div style={{ color: "var(--accent)", fontWeight: 600, marginBottom: 6 }}>We couldn’t load the corrections. Please try again.</div>
      </ReportMessage>
    );
  if (rows.length === 0)
    return (
      <ReportMessage>
        No corrections yet. This fills in as a fact-check clears a false alarm or catches a missed
        issue during an evaluation.
      </ReportMessage>
    );

  const suppress = rows.filter((r) => r.action === "suppress").length;
  const floor = rows.filter((r) => r.action === "floor").length;
  const ACTION_LABEL = { suppress: "false alarm cleared", floor: "miss caught" };
  return (
    <div>
      <div className="art-sec">
        <div className="art-h2">
          Corrections made by fact-checks <span className="cnt">{rows.length} so far</span>
        </div>
        <div className="tiles">
          {[
            { k: "Total", v: String(rows.length), d: "checked by a fact-check" },
            { k: "False alarms cleared", v: String(suppress), d: "AI flagged it, a fact-check cleared it" },
            { k: "Misses caught", v: String(floor), d: "AI missed it, a fact-check caught it" },
          ].map((t) => (
            <div className="tile" key={t.k}>
              <div className="tk">{t.k}</div>
              <div className="tv" style={{ fontSize: 18 }}>{t.v}</div>
              <div className="td">{t.d}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="art-sec" style={{ marginBottom: 4 }}>
        <div className="art-h2">Corrections <span className="cnt">{rows.length} logged</span></div>
        {rows.map((r, i) => (
          <div key={r.rollout_ref || i} style={{ padding: "9px 0", borderBottom: "1px solid var(--border)", fontSize: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "baseline" }}>
              <span style={{ fontWeight: 600 }}>{flagLabel(r.flag_code)}</span>
              <span className="cnt" style={{ color: r.action === "floor" ? "var(--accent)" : "var(--teal)" }}>{ACTION_LABEL[r.action] || r.action}</span>
            </div>
            <div style={{ color: "var(--muted)", marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
              <span>{verdictLabel(r.verdict_before)} → {verdictLabel(r.verdict_after)}</span>
              {r.contract && <span>· {r.contract}</span>}
              {(r.owner_roles || []).length > 0 && <span>· {r.owner_roles.map(roleLabel).join(", ")}</span>}
            </div>
            <div style={{ color: "var(--muted)", marginTop: 3, fontFamily: "var(--mono)", fontSize: 10.5 }}>
              {r.case_id} · {(r.rollout_ref || "").slice(0, 12)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// CHATBIND-3: the SOURCE INPUT view — what the council actually grades. Self-fetches GET /v1/case
// for the active agent + renders the transcript + the artifact GENERICALLY (JSON -> pretty; free
// text -> as-is — the shape varies by domain) + the by-construction planted label. The "look at the
// input, then run, then compare the verdict to ground truth" teaching move.
const _PRE = {
  margin: 0, padding: "11px 13px", background: "var(--surface-muted)", border: "1px solid var(--border)",
  borderRadius: "var(--r-sm)", fontFamily: "var(--mono)", fontSize: 11.5, whiteSpace: "pre-wrap",
  wordBreak: "break-word", lineHeight: 1.55, maxHeight: 300, overflow: "auto",
};

function prettyArtifact(art) {
  if (art == null || art === "") return { text: "(no artifact)", kind: "empty" };
  // an ingested artifact arrives wrapped as { raw: "<json string>" } — unwrap to the inner string.
  if (typeof art === "object" && typeof art.raw === "string") art = art.raw;
  try { return { text: JSON.stringify(JSON.parse(art), null, 2), kind: "structured" }; }
  catch { return { text: typeof art === "string" ? art : JSON.stringify(art, null, 2), kind: "free text" }; }
}

function CaseTab({ agent = "ws0_default", caseId = null, onBrowseCases }) {
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [kase, setKase] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let live = true;
    setStatus("loading");
    getCase(agent, caseId) // caseId selects a specific ingested case ("explore each case")
      .then((c) => { if (live) { setKase(c); setStatus("ready"); } })
      .catch((e) => { if (live) { setError(String(e.message || e)); setStatus("error"); } });
    return () => { live = false; };
  }, [agent, caseId]);

  if (status === "loading") return <ReportMessage>Loading the source case…</ReportMessage>;
  if (status === "error")
    return (
      <ReportMessage>
        <div style={{ color: "var(--accent)", fontWeight: 600, marginBottom: 6 }}>We couldn’t load the case. Please try again.</div>
      </ReportMessage>
    );

  const planted = kase.expected_safety_flags || [];
  const conditions = kase.conditions || [];
  const art = prettyArtifact(kase.artifact);
  return (
    <div>
      {/* FINDING #2 (UI-pass 2026-07-04): with nothing selected this tab falls back to the
          evaluation's DEFAULT case — say so, instead of silently contradicting the header's
          "No case selected" chip, and offer the jump to the browser. */}
      {caseId == null && (
        <div className="art-sec" style={{ display: "flex", gap: 10, alignItems: "baseline", fontSize: 12, color: "var(--muted)" }}>
          <span style={{ flex: 1, minWidth: 0 }}>
            Showing the evaluation’s default case — no case is selected.
          </span>
          {onBrowseCases && (
            <button className="btn btn-ghost" style={{ whiteSpace: "nowrap" }} onClick={onBrowseCases}>
              Browse cases
            </button>
          )}
        </div>
      )}
      <div className="art-sec">
        <div className="art-h2">Transcript <span className="cnt">{kase.case_id}</span></div>
        <pre style={_PRE}>{kase.transcript || "(no transcript)"}</pre>
      </div>
      {kase.artifact_text ? (
        <div className="art-sec">
          <div className="art-h2">Note <span className="cnt">the artifact (readable)</span></div>
          <pre style={_PRE}>{kase.artifact_text}</pre>
        </div>
      ) : null}
      <div className="art-sec">
        <div className="art-h2">Artifact <span className="cnt">{kase.artifact_text ? `raw · ${art.kind}` : art.kind}</span></div>
        <pre style={_PRE}>{art.text}</pre>
      </div>
      <div className="art-sec">
        <div className="art-h2">
          {kase.labeled === false ? "Expected answer" : "Planted defect"}{" "}
          <span className="cnt">{kase.labeled === false ? "not labeled · ingested data" : "by-construction ground truth"}</span>
        </div>
        {planted.length === 0 ? (
          kase.labeled === false ? (
            // HONEST-1: a BYO/unlabeled case is unknown-truth, NOT a declared clean negative.
            <div style={{ color: "var(--muted)", fontSize: 12.5 }}>No planted answer — this is your own data, graded honestly (accuracy can’t be scored without a labeled answer).</div>
          ) : (
            <div style={{ color: "var(--muted)", fontSize: 12.5 }}>clean negative — nothing planted (expected verdict: approve)</div>
          )
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {planted.map((f) => <span key={f} className="chip">{flagLabel(f)}</span>)}
          </div>
        )}
        {kase.injection_recipe ? <pre style={{ ..._PRE, marginTop: 8 }}>{JSON.stringify(kase.injection_recipe, null, 2)}</pre> : null}
      </div>
      {conditions.length > 0 && (
        <div className="art-sec">
          <div className="art-h2">Record <span className="cnt">{conditions.length} condition(s)</span></div>
          <div style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--muted)", lineHeight: 1.7 }}>
            {conditions.slice(0, 30).map((c, i) => <div key={i}>· {c}</div>)}
          </div>
        </div>
      )}
    </div>
  );
}

export function ArtifactPane({ width, full, tab, setTab, agent = "ws0_default", wsPack = null, activeCase = null, onSelectCase, selectedIds = null, onToggleSelect, onClose, onToggleFull, runStatus, runResult, runError }) {
  const titles = {
    case: ["The case", "the input, the AI’s output, and the planted answer"],
    report: ["Evaluation report", "the latest run"],
    judges: ["Reviewers", "how each one voted on this case"],
    config: ["Setup", "what the reviewers check for"],
    corpus: ["Cases & corrections", "the cases you can grade + fixes a fact-check made"],
  };
  const [t1, t2] = titles[tab];
  return (
    <section className={"artifact" + (full ? " full" : "")} style={full ? {} : { width }}>
      <div className="art-hd">
        <div className="art-toprow">
          <div style={{ minWidth: 0 }}>
            <div className="ttl">{t1}</div>
            <div className="sub">{t2}</div>
          </div>
          <div className="right">
            <button className="icon-btn" title={full ? "Exit fullscreen" : "Fullscreen"} onClick={onToggleFull}>
              <ICN name={full ? "minimize" : "expand"} size={16} />
            </button>
            <button className="icon-btn" title="Close" onClick={onClose}><ICN name="close" size={16} /></button>
          </div>
        </div>
        <div className="art-tabs">
          {[["case", "Case"], ["report", "Report"], ["judges", "Reviewers"], ["config", "Setup"], ["corpus", "Cases"]].map(([k, label]) => (
            <button key={k} className={"art-tab" + (tab === k ? " on" : "")} onClick={() => setTab(k)}>{label}</button>
          ))}
        </div>
      </div>
      <div className="art-bd">
        <div style={full ? { maxWidth: 760, margin: "0 auto" } : {}}>
          {tab === "case" && <CaseTab agent={agent} caseId={activeCase} onBrowseCases={() => setTab("corpus")} />}
          {tab === "report" && <ReportTab runStatus={runStatus} runResult={runResult} runError={runError} activeCase={activeCase} agent={agent} />}
          {tab === "judges" && <JudgeTab runStatus={runStatus} runResult={runResult} runError={runError} />}
          {tab === "config" && <ConfigTab agent={agent} wsPack={wsPack} />}
          {tab === "corpus" && <CorpusTab agent={agent} activeCase={activeCase} onSelectCase={onSelectCase} selectedIds={selectedIds} onToggleSelect={onToggleSelect} />}
        </div>
      </div>
    </section>
  );
}
