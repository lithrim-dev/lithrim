/* artifact.jsx — right-hand inspectable surface with tabs + fullscreen.
   All four tabs render REAL BFF data (WS-5d wired them off the data.jsx mocks):
     - ReportTab  — runResult.composite (threaded via props; per-run)
     - JudgeTab   — runResult.council.votes (threaded via props; per-run realized votes)
     - ConfigTab  — GET /v1/ontology (self-fetched; the standing ontology config)
     - CorpusTab  — GET /v1/corpus (self-fetched; the correction flywheel) */
import { useEffect, useState } from "react";
import { Icon as ICN } from "./icons.jsx";
import { getOntology, getCorpus } from "./bff.js";

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
  gp === "replay" ? "replay · $0" : gp === "in_process" ? "in-process · paid" : "live · paid";

function ReportMessage({ children }) {
  return (
    <div style={{ padding: "48px 16px", textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
      {children}
    </div>
  );
}

function ReportTab({ runStatus, runResult, runError }) {
  if (runStatus === "loading")
    return <ReportMessage>Running eval over the harness…</ReportMessage>;
  if (runStatus === "error")
    return (
      <ReportMessage>
        <div style={{ color: "var(--accent)", fontWeight: 600, marginBottom: 6 }}>Run failed</div>
        <div style={{ fontFamily: "var(--mono)", fontSize: 11.5 }}>{runError}</div>
        <div style={{ marginTop: 10 }}>Is the BFF up? <code>uvicorn app:app --app-dir apps/bff --port 8787</code></div>
      </ReportMessage>
    );
  if (!runResult)
    return (
      <ReportMessage>
        No run yet. Press <strong>Run eval</strong> to drive the harness and render a real report.
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
            {comp.active_findings.length} active finding(s) · {comp.grounded_adjustments.length} grounded-suppressed · {runResult.case_id}
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
            { k: "Verdict", v: comp.verdict, d: `stage ${comp.stage_verdict}` },
            { k: "Risk score", v: String(comp.score), d: "worst active severity" },
            { k: "Active findings", v: String(comp.active_findings.length), d: "after grounding" },
            { k: "Grounded suppressions", v: String(comp.grounded_adjustments.length), d: "contract-disproved" },
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
          Active findings <span className="cnt">{comp.active_findings.length}</span>
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

      {comp.grounded_adjustments.length > 0 && (
        <div className="art-sec">
          <div className="art-h2">Grounded adjustments <span className="cnt">tool-verified</span></div>
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
        <div className="art-h2">Calibration <span className="cnt">diagnostic · N={cal.n_cases}</span></div>
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
            Report-only diagnostic — not the locked calibration gate (WS-4b).
          </div>
        </div>
      </div>
    </div>
  );
}

// The realized per-judge votes the council cast on THIS case (run-eval `council`).
// Per-case truth (what each judge voted + its confidence), not a configured roster.
function JudgeTab({ runStatus, runResult, runError }) {
  if (runStatus === "loading")
    return <ReportMessage>Running the council over the harness…</ReportMessage>;
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
  return (
    <div>
      <div className="consensus" style={{ marginBottom: 18 }}>
        <div className="big">{votes.length}</div>
        <div>
          <div className="ct">{blocking ? `${blocking} blocking vote(s)` : "No blocking votes"}</div>
          <div className="cs">
            Realized votes on {runResult.case_id} · {gradeTag(runResult.grade_path)}
          </div>
        </div>
      </div>
      <div className="art-h2">Council members <span className="cnt">realized vote</span></div>
      {votes.map((v, i) => {
        const color = VOTE_COLOR[v.vote] || "var(--muted)";
        const conf = typeof v.confidence === "number" ? v.confidence : null;
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

  if (status === "loading") return <ReportMessage>Loading ontology config…</ReportMessage>;
  if (status === "error")
    return (
      <ReportMessage>
        <div style={{ color: "var(--accent)", fontWeight: 600, marginBottom: 6 }}>Could not read ontology</div>
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
          Ontology <span className="cnt">{ont.domain} · {ont.ontology_version}</span>
        </div>
        <div className="tiles">
          {[
            { k: "Flags", v: String(flags.length), d: `${gradeable} gradeable` },
            { k: "Contracts", v: String(contracts.length), d: "verification floor" },
            { k: "Block ≥", v: String(sm.block_at_or_above ?? "—"), d: "severity weight" },
            { k: "Warn >", v: String(sm.warn_above ?? "—"), d: "severity weight" },
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

// The correction-corpus / flywheel view — GET /v1/corpus (corpus-row/1). Each row is
// a logged grounding correction (suppress | floor) with before→after verdict + the
// contract + owner roles + a rollout pointer. clinical_v1 is suppress-only and the
// corpus may be empty until a run writes corrections — empty-state, never a crash.
function CorpusTab() {
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
        No corrections yet. The flywheel fills as grounding suppresses a false flag or a
        structural floor catches a missed one.
      </ReportMessage>
    );

  const suppress = rows.filter((r) => r.action === "suppress").length;
  const floor = rows.filter((r) => r.action === "floor").length;
  return (
    <div>
      <div className="art-sec">
        <div className="art-h2">
          Correction flywheel <span className="cnt">{rows.length} row(s)</span>
        </div>
        <div className="tiles">
          {[
            { k: "Corrections", v: String(rows.length), d: "tool-grounded" },
            { k: "Suppress", v: String(suppress), d: "confident FP disproved" },
            { k: "Floor", v: String(floor), d: "missed violation caught" },
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
        <div className="art-h2">Corrections <span className="cnt">corpus-row/1</span></div>
        {rows.map((r, i) => (
          <div key={r.rollout_ref || i} style={{ padding: "9px 0", borderBottom: "1px solid var(--border)", fontSize: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "baseline" }}>
              <span style={{ fontFamily: "var(--mono)", fontWeight: 600 }}>{r.flag_code}</span>
              <span className="cnt" style={{ color: r.action === "floor" ? "var(--accent)" : "var(--teal)" }}>{r.action}</span>
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

export function ArtifactPane({ width, full, tab, setTab, agent = "ws0_default", onClose, onToggleFull, runStatus, runResult, runError }) {
  const titles = {
    report: ["Evaluation report", "scribe-agent-v4 · run #218"],
    judges: ["Judge council", "per-case realized votes"],
    config: ["Config editor", "ontology · read-only"],
    corpus: ["Correction corpus", "tool-grounded flywheel"],
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
            <button className="btn btn-ghost" style={{ height: 28, padding: "0 10px" }}><ICN name="copy" size={14} /> Export</button>
            <button className="icon-btn" title={full ? "Exit fullscreen" : "Fullscreen"} onClick={onToggleFull}>
              <ICN name={full ? "minimize" : "expand"} size={16} />
            </button>
            <button className="icon-btn" title="Close" onClick={onClose}><ICN name="close" size={16} /></button>
          </div>
        </div>
        <div className="art-tabs">
          {[["report", "Report"], ["judges", "Judge council"], ["config", "Config"], ["corpus", "Corpus"]].map(([k, label]) => (
            <button key={k} className={"art-tab" + (tab === k ? " on" : "")} onClick={() => setTab(k)}>{label}</button>
          ))}
        </div>
      </div>
      <div className="art-bd">
        <div style={full ? { maxWidth: 760, margin: "0 auto" } : {}}>
          {tab === "report" && <ReportTab runStatus={runStatus} runResult={runResult} runError={runError} />}
          {tab === "judges" && <JudgeTab runStatus={runStatus} runResult={runResult} runError={runError} />}
          {tab === "config" && <ConfigTab agent={agent} />}
          {tab === "corpus" && <CorpusTab />}
        </div>
      </div>
    </section>
  );
}
