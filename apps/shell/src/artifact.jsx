/* artifact.jsx — right-hand inspectable surface with tabs + fullscreen.
   ReportTab renders the REAL eval-report from the BFF (run_eval.run() composite);
   JudgeTab/ConfigTab stay mock until WS-5d wires them. */
import { Icon as ICN } from "./icons.jsx";
import { JUDGES, CONFIG_YAML } from "./data.jsx";

// composite.verdict (reject|needs_review|approve) → banner chrome.
const VERDICT_UI = {
  approve: { icon: "check", label: "Passed quality gate", color: "var(--teal)" },
  needs_review: { icon: "flag", label: "Needs review", color: "var(--amber)" },
  reject: { icon: "flag", label: "Blocked by quality gate", color: "var(--accent)" },
};

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
  const live = runResult.grade_path === "live";

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
          <span className="cnt">{live ? "live · paid" : "replay · $0"}</span>
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

function JudgeTab() {
  return (
    <div>
      <div className="consensus" style={{ marginBottom: 18 }}>
        <div className="big">0.88</div>
        <div>
          <div className="ct">Strong council agreement</div>
          <div className="cs">Fleiss' κ across 3 judges over 2,400 samples. 94% reached the 0.66 floor on first pass.</div>
        </div>
      </div>
      <div className="art-h2">Council members <span className="cnt">weighted vote</span></div>
      {JUDGES.map((j) => (
        <div className="judge" key={j.name}>
          <div className="judge-top">
            <div className="judge-av" style={{ background: j.avc }}>{j.av}</div>
            <div style={{ minWidth: 0 }}>
              <div className="judge-name">{j.name}</div>
              <div className="judge-model">{j.model}</div>
            </div>
            <div className="judge-w"><div className="k">weight</div><div className="v">{j.weight}</div></div>
          </div>
          <div className="vbar">
            <i style={{ width: j.pass + "%", background: "var(--teal)" }} />
            <i style={{ width: j.warn + "%", background: "var(--amber)" }} />
            <i style={{ width: j.fail + "%", background: "var(--accent)" }} />
          </div>
          <div className="vbar-leg">
            <span><span className="d" style={{ background: "var(--teal)" }} /> pass {j.pass}%</span>
            <span><span className="d" style={{ background: "var(--amber)" }} /> warn {j.warn}%</span>
            <span><span className="d" style={{ background: "var(--accent)" }} /> fail {j.fail}%</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function ConfigTab() {
  return (
    <div className="editor">
      <div className="editor-hd">
        <ICN name="layers" size={14} style={{ color: "var(--accent)" }} />
        <span className="fname">eval.config.yaml</span>
        <span className="badge">read-only · synced</span>
        <button className="icon-btn" style={{ width: 26, height: 26 }}><ICN name="copy" size={14} /></button>
      </div>
      <div className="code">
        {CONFIG_YAML.map((l, i) => (
          <div className="ln" key={i}>
            <span className="gutter">{l.t === "blank" ? "" : i + 1}</span>
            {l.t === "cmt" ? (
              <span><span className="key">{l.k}</span><span className="cmt">{l.v}</span></span>
            ) : l.t === "blank" ? (
              <span>&nbsp;</span>
            ) : (
              <span>
                <span className="key">{l.k}</span>
                <span className={l.t === "str" ? "str" : l.t === "num" ? "num" : l.t === "bool" ? "bool" : ""}>{l.v}</span>
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ArtifactPane({ width, full, tab, setTab, onClose, onToggleFull, runStatus, runResult, runError }) {
  const titles = {
    report: ["Evaluation report", "scribe-agent-v4 · run #218"],
    judges: ["Judge council", "3 models · weighted vote"],
    config: ["Config editor", "eval.config.yaml"],
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
          {[["report", "Report"], ["judges", "Judge council"], ["config", "Config"]].map(([k, label]) => (
            <button key={k} className={"art-tab" + (tab === k ? " on" : "")} onClick={() => setTab(k)}>{label}</button>
          ))}
        </div>
      </div>
      <div className="art-bd">
        <div style={full ? { maxWidth: 760, margin: "0 auto" } : {}}>
          {tab === "report" && <ReportTab runStatus={runStatus} runResult={runResult} runError={runError} />}
          {tab === "judges" && <JudgeTab />}
          {tab === "config" && <ConfigTab />}
        </div>
      </div>
    </section>
  );
}
