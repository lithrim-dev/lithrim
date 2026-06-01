/* panes.jsx — left rail, center conversation (ported verbatim; placeholder mark → real logo). */
import { Icon } from "./icons.jsx";
import { Mark, Wordmark } from "./brand.jsx";
import { ConfigCard } from "./cards.jsx";
import { renderTool } from "./genui/index.js";
import { THREADS, STEPS } from "./data.jsx";

/* ============================ LEFT RAIL ============================ */
export function LeftRail({ width, active, setActive }) {
  return (
    <aside className="rail" style={{ width }}>
      <div className="rail-brand" style={{ display: "flex", alignItems: "center", height: 46, padding: "0 16px", borderBottom: "1px solid var(--border)", flex: "0 0 auto" }}>
        <Wordmark markSize={18} />
      </div>
      <div className="rail-sec">
        <div className="rail-hd">
          <span className="lbl">Evaluations</span>
          <button className="icon-btn" title="New evaluation"><Icon name="plus" size={16} /></button>
        </div>
        <div className="tb-cmd" style={{ position: "static", transform: "none", width: "100%", height: 32 }}>
          <Icon name="search" size={14} /><span>Search</span><span className="kbd">⌘K</span>
        </div>
      </div>
      <div className="rail-scroll">
        <div style={{ padding: "8px 12px 0" }}>
          {THREADS.map((t) => (
            <div key={t.id} className={"thread" + (active === t.id ? " active" : "")} onClick={() => setActive(t.id)}>
              <span className="st" style={{ background: t.color }} />
              <div className="tt">
                <div className="ti">{t.title}</div>
                <div className="ts">{t.sub}</div>
              </div>
              <div className="tm">{t.meta}</div>
            </div>
          ))}
        </div>
        <div className="journey">
          <div className="rail-hd" style={{ padding: "12px 6px 12px" }}>
            <span className="lbl">Setup journey</span>
            <span className="tm" style={{ fontFamily: "var(--mono)" }}>4 / 6</span>
          </div>
          {STEPS.map((s, i) => (
            <div key={s.name} className={"step " + s.state}>
              <div className="nodecol">
                <div className="node">{s.state === "done" ? <Icon name="check" size={12} sw={2.4} /> : i + 1}</div>
                {i < STEPS.length - 1 && <div className="line" />}
              </div>
              <div className="body-txt">
                <div className="sname">{s.name}{s.state === "current" && <span className="pill-now">NOW</span>}</div>
                <div className="sdesc">{s.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="rail-foot">
        <div className="avatar">JR</div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="who">Jordan Reyes</div>
          <div className="org">acme-health · Pro</div>
        </div>
        <button className="icon-btn"><Icon name="dots" size={16} /></button>
      </div>
    </aside>
  );
}

/* ============================ CENTER ============================ */
export function CenterPane({ onOpenArtifact, artifactOpen, onRunEval, runStatus }) {
  return (
    <main className="center">
      <div className="center-hd">
        <div style={{ minWidth: 0 }}>
          <div className="h-title">Scribe Agent v4</div>
        </div>
        <span className="chip"><span className="d" style={{ background: "var(--accent)" }} /> Run in progress</span>
        <span className="chip">2,400 samples</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button className="icon-btn" title="Refresh"><Icon name="refresh" size={16} /></button>
          {!artifactOpen && (
            <button className="btn btn-ghost" onClick={() => onOpenArtifact("report")}>
              <Icon name="panel" size={15} /> Open report
            </button>
          )}
        </div>
      </div>

      <div className="convo">
        <div className="convo-inner">

          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">setup assistant</span></div>
              <p>Welcome back. We're configuring an evaluation for <strong>Scribe Agent v4</strong>. Four of six steps are done — let's confirm the domain, then kick off the full run.</p>
              <ConfigCard onOpen={() => onOpenArtifact("config")} />
            </div>
          </div>

          <div className="msg user">
            <div className="av user">JR</div>
            <div className="content">
              <div className="name">Jordan</div>
              <p>Looks right. Bump it to the full <code className="inl">2,400</code> samples and keep the safety checks on — fabricated allergies are the one we keep failing.</p>
            </div>
          </div>

          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">setup assistant</span></div>
              <p>Done. Your <strong>judge council</strong> is three models cross-checking every verdict, with a weighted vote and a 0.66 agreement floor. Here's a sample they just scored on the 50-row dry run:</p>
              {renderTool({ type: "tool-verdict_card", state: "output-available" })}
            </div>
          </div>

          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">setup assistant</span></div>
              <p>Calibration on the dry run is tight — predicted confidence tracks observed accuracy within <strong>±3%</strong>, so the council's scores are trustworthy as a stopping signal.</p>
              {renderTool({ type: "tool-calibration_chart", state: "output-available" })}
            </div>
          </div>

          <div className="msg">
            <div className="av ai"><Mark size={17} /></div>
            <div className="content">
              <div className="name">Lithrim <span className="t">setup assistant</span></div>
              <p>Everything checks out. Running all 2,400 will take about <strong>6 minutes</strong>; I'll stream verdicts into the report as they land.</p>
              <div className="msg-actions">
                <button className="btn btn-primary" disabled={runStatus === "loading"}
                  onClick={() => onRunEval(false)}>
                  <Icon name="bolt" size={14} /> {runStatus === "loading" ? "Running…" : "Run evaluation"}
                </button>
                <button className="btn btn-ghost" onClick={() => onOpenArtifact("report")}>
                  <Icon name="panel" size={14} /> Open report
                </button>
              </div>
            </div>
          </div>

        </div>
      </div>

      <div className="composer">
        <div className="composer-inner">
          <div className="composer-box">
            <textarea rows="1" placeholder="Ask Lithrim, or describe a change to the eval…" defaultValue="" />
            <div className="composer-bar">
              <div className="left">
                <button className="icon-btn"><Icon name="attach" size={16} /></button>
                <button className="icon-btn"><Icon name="layers" size={16} /></button>
              </div>
              <span className="kbd" style={{ marginLeft: 4 }}>⌘↵ to send</span>
              <div className="send"><button className="send-btn"><Icon name="send" size={16} /></button></div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
