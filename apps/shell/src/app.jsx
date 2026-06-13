/* app.jsx — shell composition, resizable panes, theme, status bar (ported verbatim). */
import { useState, useEffect } from "react";
import { Icon as I } from "./icons.jsx";
import { LeftRail, CenterPane } from "./panes.jsx";
import { ArtifactPane } from "./artifact.jsx";
import { ModeSwitch } from "./components/ModeSwitch.jsx";

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

function TopBar({ theme, setTheme, artifactOpen, toggleArtifact, onRunEval, runStatus, mode, setMode }) {
  return (
    <div className="titlebar">
      <div className="lights"><span className="light r" /><span className="light y" /><span className="light g" /></div>
      {/* {mode && setMode && <ModeSwitch mode={mode} setMode={setMode} />} */}
      <div className="tb-crumb">
        <span className="ws-pill"><span className="dot" /> default</span>
        <span className="crumb-sep"><I name="chevR" size={14} /></span>
        <span className="crumb-txt">Evaluations <span className="crumb-sep">/</span> <b>New evaluation</b></span>
      </div>

      <div className="tb-cmd"><I name="search" size={14} /><span>Search or run a command…</span><span className="kbd">⌘K</span></div>

      <div className="tb-right">
        <button className="icon-btn" title="Toggle theme" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
          <I name={theme === "light" ? "moon" : "sun"} size={16} />
        </button>
        <button className={"icon-btn" + (artifactOpen ? " on" : "")} title="Toggle artifact panel" onClick={toggleArtifact}>
          <I name="panel" size={16} />
        </button>
        <button className="btn btn-ghost" title="One real, PAID council run — BYO key (the configured backend)"
          disabled={runStatus === "loading"} onClick={() => onRunEval(true)}>
          <I name="bolt" size={14} /> Run live
        </button>
        <button className="btn btn-primary" disabled={runStatus === "loading"} onClick={() => onRunEval(false)}>
          <I name="bolt" size={14} /> {runStatus === "loading" ? "Running…" : "Run eval"}
        </button>
      </div>
    </div>
  );
}

function StatusBar() {
  return (
    <div className="statusbar">
      <span className="si"><span className="d" style={{ background: "var(--teal)" }} /> Connected</span>
      <span className="si run-prog">
        Run #218
        <span className="pbar"><i style={{ width: "62%" }} /></span>
        1,488 / 2,400
      </span>
      <span className="si">judge council: 3 active</span>
      <div className="right">
        <span className="si">κ 0.88</span>
        <span className="si">acc 92.4%</span>
        <span className="si">v0.9.4</span>
      </div>
    </div>
  );
}

function App({ theme: themeProp, setTheme: setThemeProp, mode, setMode } = {}) {
  const [leftW, setLeftW] = useState(270);
  const [rightW, setRightW] = useState(440);
  const [open, setOpen] = useState(true);
  const [full, setFull] = useState(false);
  const [tab, setTab] = useState("report");
  // Theme is owned by root.jsx (shared with the journey) when mounted there; fall back to
  // local state when App is rendered standalone.
  const [themeLocal, setThemeLocal] = useState("light");
  const theme = themeProp ?? themeLocal;
  const setTheme = setThemeProp ?? setThemeLocal;
  // CRUD-1 (D4): the active config-plane agent + the rail's agent list (GET /v1/agents).
  // The selected agent threads into the chat (CenterPane) + the run (doRun) — no more
  // hardcoded ws0_default.
  const [activeAgent, setActiveAgent] = useState("ws0_default");
  const [agents, setAgents] = useState([]);
  // S-BS-89: "New evaluation" resets the chat to a clean slate by remounting CenterPane
  // (bumping its key clears chat + setup + showExample + input). CRUD-1 (D4) extends it to
  // also create + switch to a fresh runnable blank agent.
  const [sessionKey, setSessionKey] = useState(0);

  // The real eval-report vertical (WS-5-BFF): drive run_eval.run() via the BFF and
  // render its composite in the ReportTab. replay is the $0 default; live is one paid call.
  const [runStatus, setRunStatus] = useState("idle"); // idle | loading | ready | error
  const [runResult, setRunResult] = useState(null);
  const [runError, setRunError] = useState(null);

  const doRun = async (live = false) => {
    setRunStatus("loading");
    setRunError(null);
    setTab("report");
    setOpen(true);
    try {
      const { runEval } = await import("./bff.js");
      setRunResult(await runEval({ live, agent: activeAgent }));
      setRunStatus("ready");
    } catch (err) {
      setRunError(String(err.message || err));
      setRunStatus("error");
    }
  };

  // CRUD-1 (D4): load the config-plane agents for the rail switcher (GET /v1/agents).
  const refreshAgents = async () => {
    try {
      const { listAgents } = await import("./bff.js");
      const out = await listAgents();
      setAgents(out.agents || []);
      return out.agents || [];
    } catch {
      return [];
    }
  };
  useEffect(() => { refreshAgents(); }, []);

  // The blank-slate create: clear the chat IMMEDIATELY (UX-1's instant remount reset),
  // then create a fresh RUNNABLE empty agent (eval-N) + switch to it when the BFF responds.
  const onNewEval = async () => {
    setSessionKey((k) => k + 1); // synchronous: clean chat now (offline-safe; survives create failure)
    try {
      const { createAgent } = await import("./bff.js");
      const existing = await refreshAgents();
      let n = 1;
      while (existing.includes(`eval-${n}`)) n += 1;
      const name = `eval-${n}`;
      await createAgent(name);
      setActiveAgent(name);
      await refreshAgents();
    } catch (err) {
      console.error("New evaluation: create failed", err);
    }
  };

  const onSwitchAgent = (name) => {
    if (name === activeAgent) return;
    setActiveAgent(name);
    setSessionKey((k) => k + 1); // a switch starts a clean chat for that agent
  };

  const onDeleteAgent = async (name) => {
    try {
      const { deleteAgent } = await import("./bff.js");
      await deleteAgent(name, { rationale: "deleted via the rail (CRUD-1)" });
    } catch (err) {
      console.error("Delete agent failed (guard or 404)", err); // a 422 guard surfaces here
      return;
    }
    const left = await refreshAgents();
    if (name === activeAgent) {
      setActiveAgent(left[0] || "ws0_default");
      setSessionKey((k) => k + 1);
    }
  };

  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);

  const drag = (e, base, apply, lo, hi, invert) => {
    e.preventDefault();
    const sx = e.clientX;
    const move = (ev) => apply(clamp(base + (invert ? sx - ev.clientX : ev.clientX - sx), lo, hi));
    const up = () => {
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerup", up);
      document.body.classList.remove("resizing");
    };
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", up);
    document.body.classList.add("resizing");
  };

  const openArtifact = (t) => { setTab(t); setOpen(true); };

  return (
    <div className="desk">
      <div className="win">
        <TopBar theme={theme} setTheme={setTheme} artifactOpen={open}
          toggleArtifact={() => { setOpen((o) => !o); setFull(false); }}
          onRunEval={doRun} runStatus={runStatus} mode={mode} setMode={setMode} />
        <div className="body">
          <LeftRail width={leftW} agents={agents} activeAgent={activeAgent}
            onSwitchAgent={onSwitchAgent} onDeleteAgent={onDeleteAgent} onNewEval={onNewEval} />
          <div className="rz" onPointerDown={(e) => drag(e, leftW, setLeftW, 220, 380)} />
          <CenterPane key={sessionKey} agent={activeAgent} onOpenArtifact={openArtifact} artifactOpen={open}
            onRunEval={doRun} runStatus={runStatus}
            onRunResult={(r) => { setRunResult(r); setRunStatus("ready"); }} />
          {open && !full && (
            <div className="rz" onPointerDown={(e) => drag(e, rightW, setRightW, 340, 680, true)} />
          )}
          {open && (
            <ArtifactPane
              width={rightW} full={full} tab={tab} setTab={setTab} agent={activeAgent}
              onClose={() => { setOpen(false); setFull(false); }}
              onToggleFull={() => setFull((f) => !f)}
              runStatus={runStatus} runResult={runResult} runError={runError}
            />
          )}
        </div>
        <StatusBar />
      </div>
    </div>
  );
}

export default App;
