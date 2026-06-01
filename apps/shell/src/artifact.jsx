/* artifact.jsx — right-hand inspectable surface with tabs + fullscreen (ported verbatim). */
import { Icon as ICN } from "./icons.jsx";
import { TILES, FAILURE_MODES, JUDGES, CONFIG_YAML } from "./data.jsx";

function ReportTab() {
  return (
    <div>
      <div className="report-banner">
        <div className="rb-ic"><ICN name="check" size={20} sw={2.2} /></div>
        <div style={{ minWidth: 0 }}>
          <div className="rb-t">Passed quality gate</div>
          <div className="rb-s">2,258 of 2,400 verdicts agreed · 142 flagged for review</div>
        </div>
        <div className="rb-grade">A−</div>
      </div>

      <div className="art-sec">
        <div className="art-h2">Headline metrics</div>
        <div className="tiles">
          {TILES.map((t) => (
            <div className="tile" key={t.k}>
              <div className="tk">{t.k}</div>
              <div className="tv">{t.v}</div>
              <div className="td">
                <span className={"delta " + (t.up ? "up" : "dn")}>{t.delta}</span> {t.d}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="art-sec">
        <div className="art-h2">Failure modes <span className="cnt">142 flagged</span></div>
        {FAILURE_MODES.map((f) => (
          <div className="fmode" key={f.name}>
            <div className="fmode-top">
              <span className="fmode-name">{f.name}</span>
              <span className="fmode-val">{f.val} · {f.pct}%</span>
            </div>
            <div className="fmode-bar"><i style={{ width: f.pct + "%", background: f.color }} /></div>
          </div>
        ))}
      </div>

      <div className="art-sec" style={{ marginBottom: 4 }}>
        <div className="art-h2">By transcript category</div>
        {[
          ["Billing & refunds", "0.89", "var(--amber)"],
          ["Account access", "0.95", "var(--teal)"],
          ["Product how-to", "0.94", "var(--teal)"],
          ["Escalations", "0.86", "var(--amber)"],
        ].map(([n, v, c]) => (
          <div key={n} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, padding: "8px 0", borderBottom: "1px solid var(--border)", fontSize: 12.5 }}>
            <span style={{ whiteSpace: "nowrap" }}>{n}</span>
            <span style={{ fontFamily: "var(--mono)", fontWeight: 600, color: c }}>{v}</span>
          </div>
        ))}
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

export function ArtifactPane({ width, full, tab, setTab, onClose, onToggleFull }) {
  const titles = {
    report: ["Evaluation report", "support-agent-v4 · run #218"],
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
          {tab === "report" && <ReportTab />}
          {tab === "judges" && <JudgeTab />}
          {tab === "config" && <ConfigTab />}
        </div>
      </div>
    </section>
  );
}
