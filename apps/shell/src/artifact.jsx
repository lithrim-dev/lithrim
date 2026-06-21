/* artifact.jsx — right-hand inspectable surface with tabs + fullscreen.
   All four tabs render REAL BFF data (WS-5d wired them off the data.jsx mocks):
     - ReportTab  — runResult.composite (threaded via props; per-run)
     - JudgeTab   — runResult.council.votes (threaded via props; per-run realized votes)
     - ConfigTab  — GET /v1/ontology (self-fetched; the standing ontology config)
     - CorpusTab  — GET /v1/corpus (self-fetched; the correction flywheel) */
import { useEffect, useState } from "react";
import { Icon as ICN } from "./icons.jsx";
import { getOntology, getCorpus, getCase, listCases, getRunAudit } from "./bff.js";
import ClinicianVerdict from "./genui/ClinicianVerdict.jsx";

// composite.verdict (reject|needs_review|approve) → banner chrome.
const VERDICT_UI = {
  approve: { icon: "check", label: "Passed quality gate", color: "var(--teal)" },
  needs_review: { icon: "flag", label: "Needs review", color: "var(--amber)" },
  reject: { icon: "flag", label: "Blocked by quality gate", color: "var(--accent)" },
};

// a judge vote (PASS|WARN|FAIL|BLOCK) → chip color.
const VOTE_COLOR = {
  PASS: "var(--teal)",
  WARN: "var(--amber)",
  FAIL: "var(--accent)",
  BLOCK: "var(--accent)",
};

// grade_path → the cost tag. in_process is the OSS-standalone PAID default (LAUNCH-PREP);
// only an actual replay is $0 — never label a paid run "$0" (S-BS-110).
const gradeTag = (gp) =>
  gp === "replay" ? "Preview · $0" : gp === "in_process" ? "Full run · paid" : "Live · paid";

function ReportMessage({ children }) {
  return (
    <div style={{ padding: "48px 16px", textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
      {children}
    </div>
  );
}

function ReportTab({ runStatus, runResult, runError }) {
  if (runStatus === "loading")
    return <ReportMessage>Running the evaluation…</ReportMessage>;
  if (runStatus === "error") {
    // GRADE-GUARD-1: the BFF error format is "POST <path> → <status>: <detail>". A structured HTTP
    // response means the service IS responding (the detail is the actionable truth — e.g. "no $0
    // replay baseline — run live", or "malformed contract") — so DON'T claim it's down. Only show
    // the "unreachable, restart it" hint for a genuine no-response/network failure.
    const isHttp = /→\s*\d{3}\b/.test(String(runError || ""));
    return (
      <ReportMessage>
        <div style={{ color: "var(--accent)", fontWeight: 600, marginBottom: 6 }}>Run failed</div>
        <div style={{ fontFamily: "var(--mono)", fontSize: 11.5 }}>{runError}</div>
        {!isHttp && (
          <div style={{ marginTop: 10 }}>The evaluation service may be unreachable — ask the host to restart it.</div>
        )}
      </ReportMessage>
    );
  }
  if (!runResult)
    return (
      <ReportMessage>
        No evaluation yet. Run one to see the verdict and report here.
      </ReportMessage>
    );

  const comp = runResult.composite;
  const cal = runResult.calibration_check;
  const ui = VERDICT_UI[comp.verdict] || VERDICT_UI.needs_review;
  const gradeLabel = gradeTag(runResult.grade_path);

  return (
    <div>
      <div className="report-banner">
        <div className="rb-ic" style={{ color: ui.color }}><ICN name={ui.icon} size={20} sw={2.2} /></div>
        <div style={{ minWidth: 0 }}>
          <div className="rb-t">{ui.label}</div>
          <div className="rb-s">
            {comp.active_findings.length} issue(s) flagged · {comp.grounded_adjustments.length} false alarm(s) removed by a tool · {runResult.case_id}
          </div>
        </div>
        <div className="rb-grade" style={{ color: ui.color }}>{comp.stage_verdict}</div>
      </div>

      <div className="art-sec">
        <div className="art-h2">
          Headline metrics
          <span className="cnt">{gradeLabel}</span>
        </div>
        <div className="tiles">
          {[
            { k: "Risk score", v: String(comp.score), d: "0–1 · higher is riskier" },
            { k: "Issues flagged", v: String(comp.active_findings.length), d: "after fact-checks" },
            { k: "False alarms removed", v: String(comp.grounded_adjustments.length), d: "cleared by a tool" },
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
          Issues flagged <span className="cnt">{comp.active_findings.length}</span>
        </div>
        {comp.active_findings.length === 0 && (
          <div style={{ fontSize: 12.5, color: "var(--muted)" }}>None.</div>
        )}
        {comp.active_findings.map((f, i) => (
          <div key={i} style={{ display: "flex", gap: 8, padding: "8px 0", borderBottom: "1px solid var(--border)", fontSize: 12.5 }}>
            <ICN name="flag" size={14} style={{ color: "var(--accent)", flex: "0 0 auto", marginTop: 2 }} />
            <span style={{ fontFamily: "var(--mono)" }}>{f}</span>
          </div>
        ))}
      </div>

      {(comp.floor_adjustments || []).length > 0 && (
        <div className="art-sec">
          <div className="art-h2">Hard-rule failures <span className="cnt">a tool changed the verdict</span></div>
          {(comp.floor_adjustments || []).map((a, i) => {
            const isBlock = a.action === "floor_block";
            return (
              <div key={i} style={{ padding: "8px 0", borderBottom: "1px solid var(--border)", fontSize: 12.5 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                  <span style={{ fontFamily: "var(--mono)", fontWeight: 600, color: isBlock ? "var(--accent)" : "var(--muted)" }}>{a.flag}</span>
                  <span style={{ color: isBlock ? "var(--accent)" : "var(--muted)", whiteSpace: "nowrap" }}>
                    {isBlock ? "floor_block" : "floor_inconclusive"} · {a.contract_type}
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

      {comp.grounded_adjustments.length > 0 && (
        <div className="art-sec">
          <div className="art-h2">Corrected by a tool <span className="cnt">fact-checked</span></div>
          {comp.grounded_adjustments.map((a, i) => (
            <div key={i} style={{ padding: "8px 0", borderBottom: "1px solid var(--border)", fontSize: 12.5 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                <span style={{ fontFamily: "var(--mono)", fontWeight: 600 }}>{a.flag}</span>
                <span style={{ color: "var(--teal)", whiteSpace: "nowrap" }}>{a.action} · {a.contract}</span>
              </div>
              {a.reason && <div style={{ color: "var(--muted)", marginTop: 3 }}>{a.reason}</div>}
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

      <ClinicianVerdict runId={runResult.pipeline_run_id} councilVerdict={comp.verdict} />
    </div>
  );
}

// The realized per-judge votes the council cast on THIS case (run-eval `council`).
// Per-case truth (what each judge voted + its confidence), not a configured roster.
function JudgeTab({ runStatus, runResult, runError }) {
  // TRANSPARENCY-1 (the ClinVerdict contrast): each judge's LENS — the flags it COULD raise +
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
    return <ReportMessage>Collecting the judges' votes…</ReportMessage>;
  if (runStatus === "error")
    return (
      <ReportMessage>
        <div style={{ color: "var(--accent)", fontWeight: 600, marginBottom: 6 }}>Run failed</div>
        <div style={{ fontFamily: "var(--mono)", fontSize: 11.5 }}>{runError}</div>
      </ReportMessage>
    );
  if (!runResult)
    return (
      <ReportMessage>
        No run yet. Press <strong>Run eval</strong> to see the council's per-case votes.
      </ReportMessage>
    );

  const council = runResult.council || { votes: [], configured: [] };
  const votes = council.votes || [];
  if (votes.length === 0)
    return <ReportMessage>This run carried no per-judge council votes.</ReportMessage>;

  const blocking = votes.filter((v) => v.vote === "FAIL" || v.vote === "BLOCK").length;
  // TRANSPARENCY-1: cohort lens coverage — how many distinct flags the whole council COULD raise
  // on this case, and how many it actually did. A big "could-flag" count next to "raised 0" is the
  // blind spot, quantified (Risk-Severity Blindness: it had lenses, none covered the defect).
  const lensCodes = new Set();
  let raisedCount = 0;
  votes.forEach((v) => (lensByRole[v.judge_role] || []).forEach((c) => { lensCodes.add(c.code); if (c.raised) raisedCount += 1; }));
  return (
    <div>
      <div className="consensus" style={{ marginBottom: 18 }}>
        <div className="big">{votes.length}</div>
        <div>
          <div className="ct">{blocking ? `${blocking} blocking vote(s)` : "No blocking votes"}</div>
          <div className="cs">
            Realized votes on {runResult.case_id} · {gradeTag(runResult.grade_path)}
          </div>
          {lensCodes.size > 0 && (
            <div className="cs" style={{ marginTop: 2 }}>
              Council could flag <strong>{lensCodes.size}</strong> issue type(s) on this case ·{" "}
              <strong style={{ color: raisedCount ? "var(--accent)" : "var(--muted)" }}>raised {raisedCount}</strong>
            </div>
          )}
        </div>
      </div>
      <div className="art-h2">Council members <span className="cnt">vote · what it can flag</span></div>
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
                <div className="judge-name">{v.judge_role || "judge"}</div>
                <div className="judge-model">{v.model || "—"}</div>
              </div>
              <div className="judge-w">
                <div className="k">vote</div>
                <div className="v" style={{ color }}>{v.vote}</div>
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
              {v.reason && <span style={{ color: "var(--muted)" }}>{v.reason.slice(0, 80)}{v.reason.length > 80 ? "…" : ""}</span>}
            </div>
            {lens.length > 0 && (
              <div className="judge-lens">
                <span className="jl-k">Can flag</span>
                {lens.map((c) => (
                  <span key={c.code} className={"jl-code" + (c.raised ? " raised" : "")}>{c.code}</span>
                ))}
                <span className="jl-note" style={{ color: raised.length ? "var(--accent)" : "var(--muted)" }}>
                  {raised.length ? `raised ${raised.map((c) => c.code).join(", ")}` : "raised none"}
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
function ConfigTab({ agent = "ws0_default" }) {
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
        <div style={{ color: "var(--accent)", fontWeight: 600, marginBottom: 6 }}>Couldn’t read the setup</div>
        <div style={{ fontFamily: "var(--mono)", fontSize: 11.5 }}>{error}</div>
      </ReportMessage>
    );

  const sm = ont.severity_map || {};
  const flags = ont.flags || [];
  const contracts = ont.verification_contracts || [];
  const gradeable = flags.filter((f) => f.gradeable).length;

  return (
    <div>
      <div className="art-sec">
        <div className="art-h2">
          What the judges check <span className="cnt">{ont.domain} · {ont.ontology_version}</span>
        </div>
        <div className="tiles">
          {[
            { k: "Checks", v: String(flags.length), d: `${gradeable} scored` },
            { k: "Tool checks", v: String(contracts.length), d: "hard rules" },
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
          Flags <span className="cnt">tier · gradeable · owners</span>
        </div>
        {flags.map((f) => (
          <div key={f.flag} style={{ display: "flex", gap: 8, alignItems: "baseline", padding: "7px 0", borderBottom: "1px solid var(--border)", fontSize: 12 }}>
            <span style={{ fontFamily: "var(--mono)", fontWeight: 600, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }}>{f.flag}</span>
            <span className="cnt">{f.tier || "—"}</span>
            <span style={{ color: f.gradeable ? "var(--teal)" : "var(--muted)" }}>{f.gradeable ? "gradeable" : "reference"}</span>
            <span style={{ color: "var(--muted)", fontSize: 11 }}>{(f.owner_roles || []).length || "no"} owner(s)</span>
          </div>
        ))}
      </div>

      {contracts.length > 0 && (
        <div className="art-sec" style={{ marginBottom: 4 }}>
          <div className="art-h2">Verification contracts <span className="cnt">structural floor</span></div>
          {contracts.map((c, i) => (
            <div key={i} style={{ padding: "7px 0", borderBottom: "1px solid var(--border)", fontSize: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                <span style={{ fontFamily: "var(--mono)", fontWeight: 600 }}>{c.flag_code}</span>
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

// NARR-LOOP: the INGESTED eval corpus (GET /v1/cases) — the cases a user dropped via ingest,
// self-fetched so they SURVIVE A RELOAD (the "refresh poof": before /v1/cases they only flashed
// via the chat tool-result and vanished on reload). `has_context` surfaces the transcript-fidelity
// the 2026-06-18 ingest fix guards. Renders nothing when there are none (no empty-state noise —
// the correction flywheel below owns the empty case). Distinct from the correction corpus.
function IngestedCasesSection({ activeCase = null, onSelectCase }) {
  const [cases, setCases] = useState([]);
  const [status, setStatus] = useState("loading");
  useEffect(() => {
    let live = true;
    listCases()
      .then((b) => { if (live) { setCases(b.cases || []); setStatus("ready"); } })
      .catch(() => { if (live) setStatus("ready"); }); // offline-safe: show nothing, never crash
    return () => { live = false; };
  }, []);
  if (status !== "ready" || cases.length === 0) return null;
  const withCtx = cases.filter((c) => c.has_context).length;
  return (
    <div className="art-sec">
      <div className="art-h2">
        Eval cases <span className="cnt">{cases.length} ingested · {withCtx} with transcript</span>
      </div>
      <div style={{ fontSize: 11.5, color: "var(--muted)", margin: "0 0 6px" }}>Click a case to explore it.</div>
      {cases.map((c) => {
        const active = c.case_id === activeCase;
        return (
          <div key={c.case_id} onClick={() => onSelectCase?.(c.case_id)}
            style={{ padding: "8px 6px", margin: "0 -6px", borderBottom: "1px solid var(--border)", fontSize: 12, display: "flex", justifyContent: "space-between", gap: 10, alignItems: "baseline", cursor: onSelectCase ? "pointer" : "default", borderRadius: 6, background: active ? "var(--surface-2, rgba(127,127,127,0.10))" : "transparent" }}>
            <span style={{ fontFamily: "var(--mono)", fontWeight: active ? 600 : 400 }}>{c.case_id}</span>
            <span className="cnt" style={{ color: c.has_context ? "var(--teal)" : "var(--accent)" }}>
              {c.has_context ? "transcript ✓" : "no transcript"}{c.labeled ? " · labeled" : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// The Corpus tab = the ingested eval cases (above) + the correction flywheel (below).
function CorpusTab({ activeCase = null, onSelectCase }) {
  return (
    <div>
      <IngestedCasesSection activeCase={activeCase} onSelectCase={onSelectCase} />
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

  if (status === "loading") return <ReportMessage>Loading correction corpus…</ReportMessage>;
  if (status === "error")
    return (
      <ReportMessage>
        <div style={{ color: "var(--accent)", fontWeight: 600, marginBottom: 6 }}>Could not read corpus</div>
        <div style={{ fontFamily: "var(--mono)", fontSize: 11.5 }}>{error}</div>
      </ReportMessage>
    );
  if (rows.length === 0)
    return (
      <ReportMessage>
        No corrections yet. This fills in as a tool clears a false alarm or catches a missed
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
          Corrections made by tools <span className="cnt">{rows.length} so far</span>
        </div>
        <div className="tiles">
          {[
            { k: "Total", v: String(rows.length), d: "checked by a tool" },
            { k: "False alarms removed", v: String(suppress), d: "AI flagged it, a tool cleared it" },
            { k: "Misses caught", v: String(floor), d: "AI missed it, a tool caught it" },
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
              <span style={{ fontFamily: "var(--mono)", fontWeight: 600 }}>{r.flag_code}</span>
              <span className="cnt" style={{ color: r.action === "floor" ? "var(--accent)" : "var(--teal)" }}>{ACTION_LABEL[r.action] || r.action}</span>
            </div>
            <div style={{ color: "var(--muted)", marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontFamily: "var(--mono)" }}>{r.verdict_before} → {r.verdict_after}</span>
              {r.contract && <span>· {r.contract}</span>}
              {(r.owner_roles || []).length > 0 && <span>· {r.owner_roles.join(", ")}</span>}
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

function CaseTab({ agent = "ws0_default", caseId = null }) {
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
        <div style={{ color: "var(--accent)", fontWeight: 600, marginBottom: 6 }}>Could not read the case</div>
        <div style={{ fontFamily: "var(--mono)", fontSize: 11.5 }}>{error}</div>
      </ReportMessage>
    );

  const planted = kase.expected_safety_flags || [];
  const conditions = kase.conditions || [];
  const art = prettyArtifact(kase.artifact);
  return (
    <div>
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
            {planted.map((f) => <span key={f} className="chip">{f}</span>)}
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

export function ArtifactPane({ width, full, tab, setTab, agent = "ws0_default", activeCase = null, onSelectCase, onClose, onToggleFull, runStatus, runResult, runError }) {
  const titles = {
    case: ["The case", "the input, the AI’s output, and the planted answer"],
    report: ["Evaluation report", "the latest run"],
    judges: ["Judges", "how each one voted on this case"],
    config: ["Setup", "what the judges check for"],
    corpus: ["Cases & corrections", "the cases you loaded + fixes a tool made"],
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
          {[["case", "Case"], ["report", "Report"], ["judges", "Judges"], ["config", "Setup"], ["corpus", "Cases"]].map(([k, label]) => (
            <button key={k} className={"art-tab" + (tab === k ? " on" : "")} onClick={() => setTab(k)}>{label}</button>
          ))}
        </div>
      </div>
      <div className="art-bd">
        <div style={full ? { maxWidth: 760, margin: "0 auto" } : {}}>
          {tab === "case" && <CaseTab agent={agent} caseId={activeCase} />}
          {tab === "report" && <ReportTab runStatus={runStatus} runResult={runResult} runError={runError} />}
          {tab === "judges" && <JudgeTab runStatus={runStatus} runResult={runResult} runError={runError} />}
          {tab === "config" && <ConfigTab agent={agent} />}
          {tab === "corpus" && <CorpusTab activeCase={activeCase} onSelectCase={onSelectCase} />}
        </div>
      </div>
    </section>
  );
}
