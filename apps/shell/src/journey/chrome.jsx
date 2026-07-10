/* chrome.jsx — journey left rail, top bar, status bar, phase footer + the shared
   AgentMsg (ESM port of journeyrail.jsx; AgentMsg lifted out of jp1 since all four
   phases use it). */
import { Icon } from "../icons.jsx";
import { Mark, Wordmark } from "../brand.jsx";
import { ModeSwitch } from "../components/ModeSwitch.jsx";
import { ACTS, SCENARIOS, AGENT_TYPES } from "./journeyData.js";

/* The journey guide's message bubble — shared by all four acts. */
export function AgentMsg({ children, lead, beat }) {
  return (
    <div className="msg">
      <div className="av ai"><Mark size={17} /></div>
      <div className="content">
        <div className="name">Lithrim <span className="t">journey guide</span></div>
        {beat && <div className="beat-tag"><span className="n">{beat}</span></div>}
        {lead && <p className="lead">{lead}</p>}
        {children}
      </div>
    </div>
  );
}

export function LeftRailJ({ width, phase, setPhase, calib }) {
  let ctxTitle = "Healthcare pack", ctxItems = [];
  if (phase === 1) {
    ctxTitle = "Agent type";
    ctxItems = AGENT_TYPES.map((a) => ({ nm: a.name, vs: a.id === "scribe" ? "selected" : "", on: a.id === "scribe" }));
  } else if (phase === 2 || phase === 3) {
    ctxTitle = "Pack scenarios";
    ctxItems = SCENARIOS.map((s) => {
      const v = phase === 3 && calib === "done" ? s.after : s.before;
      return { nm: s.title, vs: v[1], color: v[0] === "PASS" ? "var(--teal)" : "var(--accent)", on: s.id === "s1" };
    });
  } else {
    ctxTitle = "Your data";
    ctxItems = [
      { nm: "SDK stream", vs: "live", color: "var(--teal)", on: true },
      { nm: "Imported logs", vs: "1,240", color: "var(--slate)" },
      { nm: "Golden cases", vs: "24", color: "var(--amber)" },
      { nm: "Regression suite", vs: "60", color: "var(--accent)" },
    ];
  }
  return (
    <aside className="rail" style={{ width }}>
      <div className="rail-brand" style={{ display: "flex", alignItems: "center", height: 46, padding: "0 16px", borderBottom: "1px solid var(--border)", flex: "0 0 auto" }}>
        <Wordmark markSize={18} />
      </div>
      <div className="rail-sec">
        <div className="tb-cmd" style={{ position: "static", transform: "none", width: "100%", height: 32 }}>
          <Icon name="search" size={14} /><span>Search</span><span className="kbd">⌘K</span>
        </div>
      </div>

      <div className="rail-scroll">
        <div className="journey" style={{ borderTop: "none", paddingTop: 14 }}>
          <div className="rail-hd" style={{ padding: "0 6px 12px" }}>
            <span className="lbl">Activation journey</span>
            <span className="tm" style={{ fontFamily: "var(--mono)" }}>{phase} / 4</span>
          </div>
          {ACTS.map((a, i) => {
            const state = a.n < phase ? "done" : a.n === phase ? "current active" : "todo";
            return (
              <div key={a.n} className={"step act " + state} onClick={() => setPhase(a.n)}>
                <div className="nodecol">
                  <div className="node">{a.n < phase ? <Icon name="check" size={12} sw={2.4} /> : a.n}</div>
                  {i < ACTS.length - 1 && <div className="line" />}
                </div>
                <div className="body-txt">
                  <div className="sname">{a.name}</div>
                  <div className="sdesc">{a.desc}</div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="rail-sec" style={{ borderTop: "1px solid var(--border)", paddingTop: 14 }}>
          <div className="rail-hd"><span className="lbl">{ctxTitle}</span></div>
          {ctxItems.map((it, i) => (
            <div className={"ctx-item" + (it.on ? " on" : "")} key={i}>
              {it.color && <span className="vd" style={{ background: it.color }} />}
              <span className="nm">{it.nm}</span>
              <span className="vs">{it.vs}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="rail-foot">
        <div className="avatar">JR</div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="who">Jordan Reyes</div>
          <div className="org">acme-health · Free</div>
        </div>
        <button className="icon-btn"><Icon name="dots" size={16} /></button>
      </div>
    </aside>
  );
}

export function TopBarJ({ theme, setTheme, panelOn, togglePanel, phase, mode, setMode }) {
  return (
    <div className="titlebar">
      <div className="lights"><span className="light r" /><span className="light y" /><span className="light g" /></div>
      {mode && setMode && <ModeSwitch mode={mode} setMode={setMode} />}
      <div className="tb-crumb">
        <span className="ws-pill"><span className="dot" /> acme-health</span>
        <span className="crumb-sep"><Icon name="chevR" size={14} /></span>
        <span className="crumb-txt">Activation <span className="crumb-sep">/</span> <b>{ACTS[phase - 1].name}</b></span>
      </div>
      <div className="tb-cmd"><Icon name="search" size={14} /><span>Search or run a command…</span><span className="kbd">⌘K</span></div>
      <div className="tb-right">
        <span className="kbd" style={{ marginRight: 2 }}>← → to navigate</span>
        <button className="icon-btn" title="Toggle theme" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
          <Icon name={theme === "light" ? "moon" : "sun"} size={16} />
        </button>
        <button className={"icon-btn" + (panelOn ? " on" : "")} title="Toggle artifact panel" onClick={togglePanel}>
          <Icon name="panel" size={16} />
        </button>
      </div>
    </div>
  );
}

export function StatusBarJ({ phase, calib }) {
  return (
    <div className="statusbar">
      <span className="si"><span className="d" style={{ background: "var(--teal)" }} /> Bench connected</span>
      <span className="si">Healthcare pack v1.2.0</span>
      <span className="si">BYOK · key local</span>
      <div className="right">
        {phase >= 3 && <span className="si">agreement {phase >= 4 || calib === "done" ? "0.91" : "0.62"}</span>}
        <span className="si">Act {phase} / 4</span>
        <span className="si">v0.9.4</span>
      </div>
    </div>
  );
}

export function PhaseFoot({ phase, setPhase }) {
  const prev = phase > 1 ? ACTS[phase - 2] : null;
  const next = phase < 4 ? ACTS[phase] : null;
  return (
    <div className="phase-foot">
      {prev
        ? <button className="btn btn-ghost pf-prev" onClick={() => setPhase(phase - 1)}><Icon name="chevR" size={14} style={{ transform: "rotate(180deg)" }} /> {prev.name}</button>
        : <span />}
      <div className="pf-spacer" />
      {next && <button className="btn btn-primary" onClick={() => setPhase(phase + 1)}>Next · {next.name} <Icon name="arrowR" size={14} /></button>}
      {!next && <span className="tag pass" style={{ height: 30, padding: "0 13px" }}><Icon name="check" size={13} /> Journey complete</span>}
    </div>
  );
}
