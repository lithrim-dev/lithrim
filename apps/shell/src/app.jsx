/* app.jsx — shell composition, resizable panes, theme, status bar (ported verbatim). */
import { useState, useEffect, useRef } from "react";
import { Icon as I } from "./icons.jsx";
import { LeftRail, CenterPane } from "./panes.jsx";
import { ArtifactPane } from "./artifact.jsx";
import { ModeSwitch } from "./components/ModeSwitch.jsx";
import { deriveSteps, nextStep } from "./journey.js";

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

// The workspace switcher (the ws-pill → a domain-setup picker). Switching a workspace
// repoints the whole config plane + the pinned pack; "New" creates one (its own config DB).
export function WorkspaceSwitcher({ active, workspaces, onSwitch, onCreate }) {
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [pack, setPack] = useState("_core");
  const [packs, setPacks] = useState([]);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) { setOpen(false); setCreating(false); }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);
  useEffect(() => {
    if (!creating) return; // load the installable/discoverable packs when the create form opens
    import("./bff.js").then(({ listPacks }) =>
      listPacks().then((r) => setPacks(r.packs || [])).catch(() => {}),
    );
  }, [creating]);
  const submit = async () => {
    const n = name.trim();
    if (!n) return;
    await onCreate(n, pack);
    setName(""); setCreating(false); setOpen(false);
  };
  const menuStyle = {
    position: "absolute", top: "calc(100% + 6px)", left: 0, minWidth: 228, zIndex: 60,
    background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 10,
    boxShadow: "var(--shadow-pop)", padding: 6,
  };
  const item = (on) => ({
    display: "flex", alignItems: "center", gap: 8, width: "100%", textAlign: "left",
    padding: "7px 9px", borderRadius: 7, fontSize: 12.5, cursor: "pointer", border: "none",
    background: on ? "var(--surface-muted)" : "transparent", color: "var(--ink)",
  });
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button className="ws-pill" title="Switch workspace" onClick={() => setOpen((o) => !o)}
        style={{ cursor: "pointer", border: "none" }}>
        <span className="dot" /> {active} <I name="chevD" size={11} />
      </button>
      {open && (
        <div style={menuStyle}>
          <div style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase",
            letterSpacing: 0.5, padding: "4px 9px 6px" }}>Workspaces</div>
          {workspaces.map((w) => (
            <button key={w.name} style={item(w.name === active)}
              onClick={() => { setOpen(false); if (w.name !== active) onSwitch(w.name); }}>
              <span className="dot" />
              <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis",
                whiteSpace: "nowrap" }}>{w.name}</span>
              <span style={{ fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--muted)" }}>{w.pack}</span>
              {w.name === active && <I name="check" size={12} />}
            </button>
          ))}
          <div style={{ height: 1, background: "var(--border)", margin: "6px 4px" }} />
          {creating ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 6, padding: "2px 4px" }}>
              <input autoFocus value={name} placeholder="workspace name"
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") submit();
                  if (e.key === "Escape") { setCreating(false); setName(""); }
                }}
                style={{ padding: "6px 8px", fontSize: 12.5, borderRadius: 6,
                  border: "1px solid var(--border)", background: "var(--bg)", color: "var(--ink)" }} />
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <select value={pack} onChange={(e) => setPack(e.target.value)}
                  title="The domain pack this workspace grades under"
                  style={{ flex: 1, minWidth: 0, padding: "6px 8px", fontSize: 12, borderRadius: 6,
                    border: "1px solid var(--border)", background: "var(--bg)", color: "var(--ink)" }}>
                  {(packs.length ? packs : [{ id: "_core", domain: "generic" }]).map((p) => (
                    <option key={p.id} value={p.id}>{p.id}{p.domain ? ` · ${p.domain}` : ""}</option>
                  ))}
                </select>
                <button onClick={submit}
                  style={{ ...item(false), width: "auto", color: "var(--accent)", fontWeight: 600 }}>Create</button>
              </div>
            </div>
          ) : (
            <button style={{ ...item(false), color: "var(--muted)" }} onClick={() => setCreating(true)}>
              <I name="plus" size={12} /> New workspace
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function TopBar({ theme, setTheme, artifactOpen, toggleArtifact, onRunEval, runStatus, mode, setMode, workspaces, activeWs, onSwitchWorkspace, onCreateWorkspace }) {
  return (
    <div className="titlebar">
      <div className="lights"><span className="light r" /><span className="light y" /><span className="light g" /></div>
      {/* {mode && setMode && <ModeSwitch mode={mode} setMode={setMode} />} */}
      <div className="tb-crumb">
        <WorkspaceSwitcher active={activeWs} workspaces={workspaces}
          onSwitch={onSwitchWorkspace} onCreate={onCreateWorkspace} />
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

// Live status bar — wired to GET /v1/meta (the active workspace's real state), not demo numbers.
function StatusBar({ activeWs }) {
  const [meta, setMeta] = useState(null);
  const [connected, setConnected] = useState(true);
  useEffect(() => {
    let alive = true;
    const load = () =>
      import("./bff.js").then(({ getMeta }) =>
        getMeta()
          .then((m) => alive && (setMeta(m), setConnected(true)))
          .catch(() => alive && setConnected(false)),
      );
    load();
    const t = setInterval(load, 4000); // reflect workspace switches / new agents / new runs
    return () => { alive = false; clearInterval(t); };
  }, [activeWs]);
  const plural = (n, s) => `${n} ${s}${n === 1 ? "" : "s"}`;
  return (
    <div className="statusbar">
      <span className="si">
        <span className="d" style={{ background: connected ? "var(--teal)" : "var(--amber)" }} />
        {connected ? "Connected" : "Connecting…"}
      </span>
      {meta && <span className="si">{meta.workspace} · {meta.pack}</span>}
      {meta && <span className="si">{plural(meta.agents, "agent")}</span>}
      {meta && <span className="si">judge council: {meta.judges}</span>}
      <div className="right">
        {meta && <span className="si">{plural(meta.runs, "run")}</span>}
        {meta && <span className="si">v{meta.version}</span>}
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
  // Default ws0_default; honor a ?agent= deep-link (mirrors root.jsx's ?demo) so a sales/demo
  // capture can land directly on a specific agent — no rail click, so no CenterPane remount race.
  const [activeAgent, setActiveAgent] = useState(() => {
    try { return new URLSearchParams(window.location.search).get("agent") || "ws0_default"; }
    catch { return "ws0_default"; }
  });
  const [agents, setAgents] = useState([]);
  // SHEPHERD-1 (W1): the live PLAN surface — the active agent's config (GET /v1/agent)
  // + the run history (GET /v1/runs) the rail derivation reads. refreshJourney() re-fetches
  // both; deriveSteps(...) turns them into the rail steps + the "N / total" count.
  const [agentCfg, setAgentCfg] = useState(null);
  const [runs, setRuns] = useState([]);
  // S-BS-89: "New evaluation" resets the chat to a clean slate by remounting CenterPane
  // (bumping its key clears chat + setup + showExample + input). CRUD-1 (D4) extends it to
  // also create + switch to a fresh runnable blank agent.
  const [sessionKey, setSessionKey] = useState(0);
  // P2: the active workspace (the switchable domain setup) + its switcher.
  const [workspaces, setWorkspaces] = useState([]);
  const [activeWs, setActiveWs] = useState("default");

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
      refreshJourney(); // W1: a run flips Run/Review done in the rail
    } catch (err) {
      setRunError(String(err.message || err));
      setRunStatus("error");
    }
  };

  // SHEPHERD-1 (W1): re-fetch the live plan state (the active agent's config + the run
  // history) so the rail re-derives. Called on mount, on activeAgent change, after a run,
  // after a workspace/agent switch, AND on the W3 save signal (onConfigSaved). Offline-safe.
  const refreshJourney = async () => {
    try {
      const { getAgent, getRuns } = await import("./bff.js");
      const [cfg, runHist] = await Promise.all([
        getAgent(activeAgent).catch(() => null),
        getRuns().then((r) => r.runs || []).catch(() => []),
      ]);
      setAgentCfg(cfg);
      setRuns(runHist);
    } catch { /* offline-safe */ }
  };
  useEffect(() => { refreshJourney(); }, [activeAgent]);

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

  // SHEPHERD-1b (W1, S-BS-149): converge the rail onto the SAME agent the chat shepherd
  // resolves. The shell defaults activeAgent to ws0_default (or a ?agent= deep-link), but a
  // non-default workspace's agents may not include it — so the rail derived a blank "0/5" for
  // a phantom agent while the shepherd (_resolve_chat_agent) operated the workspace's first
  // agent. This mirrors that BFF contract EXACTLY: a valid activeAgent (incl. a valid deep-link)
  // is honored; an absent one coerces to agents[0]; an empty list is left unchanged (no crash).
  // setActiveAgent ONLY — it never bumps sessionKey (the sole CenterPane remount trigger), and
  // it is idempotent (once activeAgent ∈ agents the condition is false, so no flip-flop).
  useEffect(() => {
    if (agents.length > 0 && !agents.includes(activeAgent)) setActiveAgent(agents[0]);
  }, [agents]); // eslint-disable-line react-hooks/exhaustive-deps

  // P2: load the workspaces for the switcher on mount.
  const refreshWorkspaces = async () => {
    try {
      const { listWorkspaces } = await import("./bff.js");
      const out = await listWorkspaces();
      setWorkspaces(out.workspaces || []);
      setActiveWs(out.active || "default");
    } catch { /* offline-safe */ }
  };
  useEffect(() => { refreshWorkspaces(); }, []);

  // Switching a workspace repoints the whole config plane server-side — reload the agents,
  // reset the active agent, and clear the run so the UI reflects the new domain.
  const reloadForWorkspace = async () => {
    const left = await refreshAgents();
    setActiveAgent(left[0] || "ws0_default");
    setRunResult(null); setRunStatus("idle"); setRunError(null);
    setSessionKey((k) => k + 1);
  };
  const onSwitchWorkspace = async (name) => {
    if (name === activeWs) return;
    try {
      const { switchWorkspace } = await import("./bff.js");
      await switchWorkspace(name);
    } catch (err) { console.error("Switch workspace failed", err); return; }
    setActiveWs(name);
    await reloadForWorkspace();
  };
  const onCreateWorkspace = async (name, pack = "_core") => {
    try {
      const { createWorkspace, switchWorkspace } = await import("./bff.js");
      await createWorkspace({ name, pack });
      await switchWorkspace(name);
    } catch (err) { console.error("Create workspace failed", err); return; }
    setActiveWs(name);
    await refreshWorkspaces();
    await reloadForWorkspace();
  };

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

  // SHEPHERD-1 (W1): derive the rail's plan from the live state. Review `done` ⟺ a run
  // result is loaded/viewed (runResult non-null) — a distinct guided beat past Run.
  const journey = deriveSteps(agentCfg, runs, activeAgent, runResult);

  return (
    <div className="desk">
      <div className="win">
        <TopBar theme={theme} setTheme={setTheme} artifactOpen={open}
          toggleArtifact={() => { setOpen((o) => !o); setFull(false); }}
          onRunEval={doRun} runStatus={runStatus} mode={mode} setMode={setMode}
          workspaces={workspaces} activeWs={activeWs}
          onSwitchWorkspace={onSwitchWorkspace} onCreateWorkspace={onCreateWorkspace} />
        <div className="body">
          <LeftRail width={leftW} agents={agents} activeAgent={activeAgent}
            onSwitchAgent={onSwitchAgent} onDeleteAgent={onDeleteAgent} onNewEval={onNewEval}
            steps={journey.steps} journeyCount={{ done: journey.done, total: journey.total }} />
          <div className="rz" onPointerDown={(e) => drag(e, leftW, setLeftW, 220, 380)} />
          <CenterPane key={sessionKey} agent={activeAgent} onOpenArtifact={openArtifact} artifactOpen={open}
            onRunEval={doRun} runStatus={runStatus}
            onRunResult={(r) => { setRunResult(r); setRunStatus("ready"); }}
            onConfigSaved={refreshJourney} nextStepName={nextStep(journey)} />
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
        <StatusBar activeWs={activeWs} />
      </div>
    </div>
  );
}

export default App;
