/* app.jsx — shell composition, resizable panes, theme, status bar (ported verbatim). */
import { useState, useEffect, useRef, useSyncExternalStore } from "react";
import { Icon as I } from "./icons.jsx";
import { LeftRail, CenterPane } from "./panes.jsx";
import { ArtifactPane } from "./artifact.jsx";
import { ModeSwitch } from "./components/ModeSwitch.jsx";
import { CostModal } from "./components/CostModal.jsx";
import { CommandPalette } from "./palette.jsx";
import { deriveSteps, nextStep, isSampleLeaked } from "./journey.js";
import { subscribeProgress, getProgress } from "./progress.js"; // GRADE-PROGRESS-1: the batch-grade in-flight chip

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

// The workspace switcher (the ws-pill → a domain-setup picker). Switching a workspace
// repoints the whole config plane + the pinned pack; "New" creates one (its own config DB).
export function WorkspaceSwitcher({ active, workspaces, onSwitch, onCreate }) {
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [pack, setPack] = useState("_core");
  const [packs, setPacks] = useState([]);
  const [err, setErr] = useState(null); // F1: surface invalid-name validation + the server reject inline
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
  // F1: validate client-side against the SAME rule the server enforces (alphanumerics, '-', '_')
  // BEFORE the call, then surface a server reject (400) inline too — never silently swallow it.
  const submit = async () => {
    const n = name.trim();
    if (!n) return;
    if (!/^[A-Za-z0-9_-]+$/.test(n)) {
      setErr("Use letters, digits, '-' or '_' only (no spaces).");
      return;
    }
    try {
      await onCreate(n, pack);
    } catch (e) {
      setErr(String(e?.message || e) || "Create workspace failed.");
      return;
    }
    setName(""); setErr(null); setCreating(false); setOpen(false);
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
                onChange={(e) => { setName(e.target.value); if (err) setErr(null); }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") submit();
                  if (e.key === "Escape") { setCreating(false); setName(""); setErr(null); }
                }}
                style={{ padding: "6px 8px", fontSize: 12.5, borderRadius: 6,
                  border: "1px solid var(--border)", background: "var(--bg)", color: "var(--ink)" }} />
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <select value={pack} onChange={(e) => setPack(e.target.value)}
                  title="The domain pack this workspace grades under"
                  style={{ flex: 1, minWidth: 0, padding: "6px 8px", fontSize: 12, borderRadius: 6,
                    border: "1px solid var(--border)", background: "var(--bg)", color: "var(--ink)" }}>
                  {/* dedupe id==domain — "clinical_scribe · clinical_scribe" read as a glitch */}
                  {(packs.length ? packs : [{ id: "_core", domain: "generic" }]).map((p) => (
                    <option key={p.id} value={p.id}>{p.id}{p.domain && p.domain !== p.id ? ` · ${p.domain}` : ""}</option>
                  ))}
                </select>
                <button onClick={submit}
                  style={{ ...item(false), width: "auto", color: "var(--accent)", fontWeight: 600 }}>Create</button>
              </div>
              {err && (
                <div data-testid="ws-create-error" role="alert"
                  style={{ fontSize: 11.5, color: "var(--accent)", lineHeight: 1.35 }}>{err}</div>
              )}
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

// CONN-1: the registry-driven connector form (a popover off a toolbar pill, mirrors
// WorkspaceSwitcher). The data source is PICKED from GET /v1/connectors (the active pack's declared
// ingest connectors — no hardcoded source); base URL + a MASKED key + a read-only Test surfacing
// the 200/401/timeout status; on a clean Test the key is written server-side to .connector_env
// (never the response), then "Pull a batch" → POST /v1/connector/ingest dispatches by connector_id
// and ingests real-field cases ($0 — the floor-grade is NARR-7). Hand-compact JSX, no prettier.
export function ConnectorForm() {
  const [open, setOpen] = useState(false);
  const [baseUrl, setBaseUrl] = useState("");
  const [key, setKey] = useState("");
  const [limit, setLimit] = useState(50);
  const [status, setStatus] = useState(null); // {kind:"ok"|"err"|"ingested", msg}
  const [busy, setBusy] = useState(false);
  const [connectors, setConnectors] = useState([]); // CONN-1: registry-driven, GET /v1/connectors
  const [selected, setSelected] = useState("");
  const ref = useRef(null);
  // CONN-1: load the declared ingest connectors when the popover opens (no hardcoded source).
  useEffect(() => {
    if (!open || connectors.length) return;
    (async () => {
      try {
        const { listConnectors } = await import("./bff.js");
        const list = (await listConnectors()).connectors || [];
        setConnectors(list);
        if (list.length && !selected) {
          setSelected(list[0].connector_id);
          if (list[0].default_base_url) setBaseUrl(list[0].default_base_url);
        }
      } catch { /* leave empty → the popover shows the no-connectors hint */ }
    })();
  }, [open, connectors.length, selected]);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);
  const test = async () => {
    if (!selected || !baseUrl.trim() || !key.trim()) return;
    setBusy(true); setStatus(null);
    try {
      const { testConnector } = await import("./bff.js");
      const r = await testConnector({ base_url: baseUrl.trim(), x_api_key: key.trim(), connector_id: selected });
      setStatus(r.status === 200
        ? { kind: "ok", msg: `Connected · tested ${r.last_tested || ""}` }
        : { kind: "err", msg: r.error || `status ${r.status}` });
    } catch (e) { setStatus({ kind: "err", msg: String(e.message || e) }); }
    finally { setBusy(false); }
  };
  const pull = async () => {
    if (!selected) return;
    setBusy(true); setStatus(null);
    try {
      const { ingestConnector } = await import("./bff.js");
      const r = await ingestConnector({ connector_id: selected, limit: Number(limit) || 50 });
      setStatus({ kind: "ingested",
        msg: `Ingested ${r.count} case(s) from ${r.sessions} session(s)${r.errors_trapped ? ` · ${r.errors_trapped} trapped` : ""}` });
    } catch (e) { setStatus({ kind: "err", msg: String(e.message || e) }); }
    finally { setBusy(false); }
  };
  const menuStyle = {
    position: "absolute", top: "calc(100% + 6px)", left: 0, minWidth: 280, zIndex: 60,
    background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 10,
    boxShadow: "var(--shadow-pop)", padding: 10, display: "flex", flexDirection: "column", gap: 7,
  };
  const inputStyle = {
    padding: "6px 8px", fontSize: 12.5, borderRadius: 6, border: "1px solid var(--border)",
    background: "var(--bg)", color: "var(--ink)",
  };
  const btn = (primary) => ({
    padding: "6px 10px", fontSize: 12, borderRadius: 6, border: "none", cursor: "pointer",
    background: primary ? "var(--accent)" : "var(--surface-muted)",
    color: primary ? "#fff" : "var(--ink)", fontWeight: 600,
  });
  const statusColor = status?.kind === "err" ? "var(--amber)" : "var(--teal)";
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button className="ws-pill" title="Connect a data source (pick from the pack's connectors)"
        onClick={() => setOpen((o) => !o)} style={{ cursor: "pointer", border: "none" }}>
        <I name="link" size={11} /> Connector <I name="chevD" size={11} />
      </button>
      {open && (
        <div style={menuStyle}>
          <div style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase",
            letterSpacing: 0.5 }}>Data source</div>
          {connectors.length === 0 ? (
            <div style={{ fontSize: 11.5, color: "var(--muted)" }}>No connectors for this workspace.</div>
          ) : (
            <select value={selected} onChange={(e) => {
              setSelected(e.target.value);
              const c = connectors.find((x) => x.connector_id === e.target.value);
              if (c && c.default_base_url) setBaseUrl(c.default_base_url);
            }} style={inputStyle}>
              {connectors.map((c) => <option key={c.connector_id} value={c.connector_id}>{c.label}</option>)}
            </select>
          )}
          <input value={baseUrl} placeholder="base URL (https://…)"
            onChange={(e) => setBaseUrl(e.target.value)} style={inputStyle} />
          <input type="password" value={key} placeholder="x-api-key (write-only, masked)"
            autoComplete="off" onChange={(e) => setKey(e.target.value)} style={inputStyle} />
          <div style={{ display: "flex", gap: 6 }}>
            <button onClick={test} disabled={busy || !selected} style={btn(false)}>Test connection</button>
          </div>
          <div style={{ height: 1, background: "var(--border)", margin: "2px 0" }} />
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="number" min="1" value={limit} onChange={(e) => setLimit(e.target.value)}
              title="how many sessions to pull" style={{ ...inputStyle, width: 70 }} />
            <button onClick={pull} disabled={busy || !selected} style={btn(true)}>Pull a batch</button>
          </div>
          {status && <div style={{ fontSize: 11.5, color: statusColor }}>{status.msg}</div>}
        </div>
      )}
    </div>
  );
}

function TopBar({ theme, setTheme, artifactOpen, toggleArtifact, onRunEval, runStatus, mode, setMode, workspaces, activeWs, onSwitchWorkspace, onCreateWorkspace, onOpenPalette }) {
  return (
    <div className="titlebar">
      {/* <div className="lights"><span className="light r" /><span className="light y" /><span className="light g" /></div> */}
      {/* {mode && setMode && <ModeSwitch mode={mode} setMode={setMode} />} */}
      <div className="tb-crumb">
        <WorkspaceSwitcher active={activeWs} workspaces={workspaces}
          onSwitch={onSwitchWorkspace} onCreate={onCreateWorkspace} />
        {/* <span className="crumb-sep"><I name="chevR" size={14} /></span>
        <ConnectorForm /> */}
        <span className="crumb-sep"><I name="chevR" size={14} /></span>
        <span className="crumb-txt"><b>Evaluations</b></span>
      </div>

      {/* CMDK-1: was an inert div advertising ⌘K — now it opens the real command palette. */}
      <button type="button" className="tb-cmd" onClick={onOpenPalette}
        title="Search cases & evaluations, or run a command (⌘K)">
        <I name="search" size={14} /><span>Search or run a command…</span><span className="kbd">⌘K</span>
      </button>

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
      import("./bff.js")
        .then(({ getMeta }) => getMeta())
        .then((m) => alive && (setMeta(m), setConnected(true)))
        .catch(() => alive && setConnected(false));
    load();
    const t = setInterval(load, 4000); // reflect workspace switches / new agents / new runs
    return () => { alive = false; clearInterval(t); };
  }, [activeWs]);
  // GRADE-PROGRESS-1: the module-store chip — the cohort grade is one multi-minute POST; this is
  // the persistent chrome signal it is still running (lives here, outside the modal/pane chrome).
  const prog = useSyncExternalStore(subscribeProgress, getProgress);
  const plural = (n, s) => `${n} ${s}${n === 1 ? "" : "s"}`;
  return (
    <div className="statusbar">
      <span className="si">
        <span className="d" style={{ background: connected ? "var(--teal)" : "var(--amber)" }} />
        {connected ? "Connected" : "Connecting…"}
      </span>
      {prog.active && (
        <span className="si" data-testid="grade-progress">
          <span className="d" style={{ background: "var(--accent)" }} />
          {prog.total
            ? (prog.done ? `${prog.label} ${prog.done}/${prog.total}…` : `${prog.label} ${plural(prog.total, "case")}…`)
            : `${prog.label}…`}
        </span>
      )}
      {meta && <span className="si">{meta.workspace} · {meta.pack}</span>}
      {meta && <span className="si">{plural(meta.agents, "agent")}</span>}
      {meta && <span className="si">judges: {meta.judges}</span>}
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
  // CONV-FIRST (SPEC_CONVERSATIONAL_FIRST): the auxiliary artifact pane is CLOSED by default —
  // the center conversation is the product surface. The pane opens only on an explicit
  // drill-down (an inline card's "Open full →"/onOpenArtifact, the manual Run button, or an
  // agent open_artifact directive gated to explicit detail). The conversational run path
  // (CenterPane → onRunResult) renders inline and never opens it.
  const [open, setOpen] = useState(false);
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
  // EVAL-FLOW (W1a/E-D1 option i): the active agent's ontology verification_contracts — the
  // SAME store the grade consumes. A saved grounding contract ticks the rail's Ground-truth step
  // honestly (no eval_profile.tools stuffing). refreshJourney re-fetches it alongside cfg+runs.
  const [contracts, setContracts] = useState([]);
  // READINESS preflight: the active agent↔pinned-pack report (GET /v1/agents/{agent}/readiness).
  // Surfaces the silent hole where a pack-declared fact-check can't run for this agent. Fed inline
  // to CenterPane (setup-gaps card + the paid-run warning) and to the rail's Ground-truth predicate.
  const [readiness, setReadiness] = useState(null);
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
  // The case a viewer is exploring / running — chosen from the ingested corpus (the Cases tab) or
  // named/shown in the chat. null → the agent's own dataset.case_id (back-compat). ACTIVE-CASE-1:
  // we do NOT silently default to the first corpus case — that made "this case" resolve to an
  // arbitrary, invisible case (incoherent cold-open). It stays null until the user names/picks a
  // case (the chat's None-branch then calls list_cases + asks); the header shows the active case.
  const [activeCase, setActiveCase] = useState(null);
  // COHORT-SUBSET-1: the Cases-browser MULTI-select — a lifted Set the browser toggles (checkbox) and
  // the "Run selected (N)" cohort trigger reads. Single-select arming (activeCase) is untouched: an
  // EMPTY set = today's behavior. Lifted here so it's the same shared state panes/palette can read.
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const onToggleSelect = (cid) =>
    setSelectedIds((prev) => { const next = new Set(prev); if (next.has(cid)) next.delete(cid); else next.add(cid); return next; });
  const refreshCases = async () => {
    try {
      const { listCases } = await import("./bff.js");
      return (await listCases()).cases || [];
    } catch { return []; }
  };
  useEffect(() => { refreshCases(); }, [activeWs]); // eslint-disable-line react-hooks/exhaustive-deps
  const onSelectCase = (cid) => { setActiveCase(cid); setTab("case"); setOpen(true); };

  const doRun = async (live = false, caseId = null) => {
    const cid = caseId ?? activeCase;
    setRunStatus("loading");
    setRunError(null);
    if (caseId) setActiveCase(caseId); // SCORECARD-CLICK: a row picks the case it runs
    setTab("report");
    setOpen(true);
    try {
      const { runEval } = await import("./bff.js");
      setRunResult(await runEval({ live, agent: activeAgent, case_id: cid }));
      setRunStatus("ready");
      refreshJourney(); // W1: a run flips Run/Review done in the rail
    } catch (err) {
      setRunError(String(err.message || err));
      setRunStatus("error");
    }
  };
  // S-BS-80: a live run is PAID — every entry point routes through the in-DOM cost confirm
  // (the same CostModal contract as the chat/composer paid paths; never window.confirm).
  // $0 replays pass straight through. `liveConfirm` holds the pending case id (or true).
  const [liveConfirm, setLiveConfirm] = useState(null);

  // CMDK-1: the ⌘K command palette — the real thing behind both search affordances (the
  // top-bar bar opens it directly; the rail's dispatches "lithrim:cmdk"). Every action is
  // an EXISTING App callback, so the paid entry still lands on the S-BS-80 cost confirm.
  const [paletteOpen, setPaletteOpen] = useState(false);
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && String(e.key).toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    const onOpen = () => setPaletteOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("lithrim:cmdk", onOpen);
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("lithrim:cmdk", onOpen); };
  }, []);
  const requestRun = (live = false, caseId = null) => {
    if (live) { setLiveConfirm({ caseId }); return; }
    doRun(false, caseId);
  };

  // SHEPHERD-1 (W1): re-fetch the live plan state (the active agent's config + the run
  // history) so the rail re-derives. Called on mount, on activeAgent change, after a run,
  // after a workspace/agent switch, AND on the W3 save signal (onConfigSaved). Offline-safe.
  const refreshJourney = async () => {
    try {
      const { getAgent, getRuns, getOntology, getReadiness } = await import("./bff.js");
      const [cfg, runHist, ont, ready] = await Promise.all([
        getAgent(activeAgent).catch(() => null),
        getRuns().then((r) => r.runs || []).catch(() => []),
        getOntology(activeAgent).catch(() => null), // EVAL-FLOW (W1a): the grade's grounding store
        getReadiness(activeAgent).catch(() => null), // READINESS: agent↔pack contract coverage
      ]);
      setAgentCfg(cfg);
      setRuns(runHist);
      setContracts((ont && ont.verification_contracts) || []);
      setReadiness(ready);
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
    resetEvalState(); // E1: clear run + active case (ACTIVE-CASE-1: no silent first-case pick)
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
    } catch (err) { console.error("Create workspace failed", err); throw err; } // F1: re-throw so the switcher surfaces it inline
    setActiveWs(name);
    await refreshWorkspaces();
    await reloadForWorkspace();
  };

  // The blank-slate create: clear the chat IMMEDIATELY (UX-1's instant remount reset),
  // then create a fresh RUNNABLE empty agent (eval-N) + switch to it when the BFF responds.
  const onNewEval = async () => {
    setSessionKey((k) => k + 1); // synchronous: clean chat now (offline-safe; survives create failure)
    resetEvalState(); // E1: a fresh evaluation starts clean — drop the prior agent's run/case from the panes
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

  // STATE-SYNC (E1): the shared run + case state is per-agent — switching or deleting the
  // active agent must clear it so the three panes (conversation, rail, side panel) agree on
  // WHICH agent/case/run they show. Without this, the Report/Reviewers tabs bled the prior
  // agent's verdict and the header chip kept its case. reloadForWorkspace (workspace switch)
  // already did this inline; this is the same reset, factored so every switch path reuses it.
  const resetEvalState = () => {
    setRunResult(null); setRunStatus("idle"); setRunError(null);
    setActiveCase(null);
  };

  const onSwitchAgent = (name) => {
    if (name === activeAgent) return;
    setActiveAgent(name);
    resetEvalState(); // E1: clear the prior agent's run/case so the panes don't bleed it
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
      resetEvalState(); // E1: the active agent is gone — clear its run/case from the panes
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
  // EVAL-FLOW (W1a): `contracts` (the ontology verification_contracts) ticks Ground truth.
  // F2 (+ refine): a freshly-created (non-default) workspace re-seeds the `ws0_default` SAMPLE
  // on the first GET /v1/agents read, so its pre-baked profile (ontology + judges) would show
  // stale Domain✓/Judges✓ progress the user never set → derive against blank state. BUT once
  // the sample has been genuinely graded on THIS workspace (a run for it — `runs` is the active
  // workspace's, server-scoped by out_dir), it is a real evaluation, not a leaked seed, so its
  // true journey shows. `isSampleLeaked` (journey.js) is the pure, unit-tested predicate.
  const sampleLeaked = isSampleLeaked(activeWs, activeAgent, runs);
  const journey = deriveSteps(
    sampleLeaked ? null : agentCfg, runs, activeAgent, runResult,
    sampleLeaked ? [] : contracts,
    sampleLeaked ? null : readiness, // READINESS: a pack-declared floor the agent can't run un-ticks Ground truth
  );

  // F3: the active workspace's pinned domain pack — so the Setup tab can tell whether the
  // self-fetched ontology truly belongs to this workspace or is the leaked `_core` seed sample.
  const wsPack = (workspaces.find((w) => w.name === activeWs) || {}).pack || null;

  // CMDK-1: the palette's command set — thin wrappers over the App's existing callbacks
  // (nothing here spends: "Run live" goes to requestRun(true) → the S-BS-80 cost confirm).
  const paletteActions = [
    { id: "run-eval", label: "Run eval — replay the selected case for $0", run: () => requestRun(false) },
    { id: "run-live", label: "Run live — one real, paid council run", hint: "cost-confirmed", run: () => requestRun(true) },
    // COHORT-SUBSET-1: a NON-chat "Grade all cases" — dispatch the same lithrim:grade-cohort bridge
    // (no case_ids = ALL) the CenterPane opens the cohort cost-confirm for. cohort grading is no
    // longer chat-only; the confirm is still the sole paid path (the palette itself never spends).
    { id: "grade-all", label: "Grade all cases — one paid cohort batch", hint: "cost-confirmed", run: () => { try { window.dispatchEvent(new CustomEvent("lithrim:grade-cohort", { detail: {} })); } catch {} } },
    { id: "explore-case", label: "Explore case — browse the gradeable cases", run: () => openArtifact(activeCase ? "case" : "corpus") },
    // RELIABILITY-CARD-1: a NON-chat "Show reliability" — dispatch the lithrim:show-reliability
    // bridge (same idiom as lithrim:grade-cohort) the CenterPane fetches GET /v1/reliability/{agent}
    // for and renders the tool-reliability_card INLINE. $0 pure read; adds NO agent tool (the
    // len(_TOOL_SPECS)==24 pin stays green — the card is emitted by the shell, not the agent).
    { id: "show-reliability", label: "Reliability metrics — kappa · calibration · floor selective-prediction", run: () => { try { window.dispatchEvent(new CustomEvent("lithrim:show-reliability")); } catch {} } },
    // SWEEP (RIGOR-1 / Q1 — NEW-G3): a NON-chat "Reliability sweep" — dispatch the lithrim:show-sweep
    // bridge (same idiom as show-reliability) the CenterPane fetches GET /v1/reliability/{agent}/sweep
    // for and renders the tool-sweep_card INLINE. $0 pure read; adds NO agent tool (the pin stays 24 —
    // the card is emitted by the shell, not the agent).
    { id: "show-sweep", label: "Reliability sweep — self-consistency across K samples (flip-rate · convergence · variance)", run: () => { try { window.dispatchEvent(new CustomEvent("lithrim:show-sweep")); } catch {} } },
    { id: "open-report", label: "Open report — the latest run's verdict", run: () => openArtifact("report") },
    { id: "new-eval", label: "New evaluation", run: onNewEval },
    { id: "connect-ai", label: "Connect AI — providers & model assignments", run: () => { try { window.dispatchEvent(new CustomEvent("lithrim:connect-ai")); } catch {} } },
    { id: "toggle-theme", label: `Switch to the ${theme === "light" ? "dark" : "light"} theme`, run: () => setTheme(theme === "light" ? "dark" : "light") },
  ];

  return (
    <div className="desk">
      <div className="win">
        <TopBar theme={theme} setTheme={setTheme} artifactOpen={open}
          toggleArtifact={() => { setOpen((o) => !o); setFull(false); }}
          onRunEval={requestRun} runStatus={runStatus} mode={mode} setMode={setMode}
          workspaces={workspaces} activeWs={activeWs}
          onSwitchWorkspace={onSwitchWorkspace} onCreateWorkspace={onCreateWorkspace}
          onOpenPalette={() => setPaletteOpen(true)} />
        <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)}
          actions={paletteActions} agents={agents} activeAgent={activeAgent}
          onSwitchAgent={onSwitchAgent} onSelectCase={onSelectCase} agent={activeAgent} />
        <CostModal
          open={liveConfirm != null}
          title="Run a live, paid evaluation?"
          body="This runs one real, paid evaluation (model calls you'll be billed for). Run eval (without live) replays the saved baseline for free."
          confirmLabel="Run live (paid)"
          onConfirm={() => { const cid = liveConfirm?.caseId ?? null; setLiveConfirm(null); doRun(true, cid); }}
          onCancel={() => setLiveConfirm(null)} />
        <div className="body">
          <LeftRail width={leftW} agents={agents} activeAgent={activeAgent}
            onSwitchAgent={onSwitchAgent} onDeleteAgent={onDeleteAgent} onNewEval={onNewEval}
            steps={journey.steps} journeyCount={{ done: journey.done, total: journey.total }} />
          <div className="rz" onPointerDown={(e) => drag(e, leftW, setLeftW, 220, 380)} />
          <CenterPane key={sessionKey} agent={activeAgent} onOpenArtifact={openArtifact} artifactOpen={open}
            onRunEval={requestRun} runStatus={runStatus}
            onOpenCaseRun={(cid) => doRun(false, cid)}
            activeCase={activeCase} onActiveCase={setActiveCase}
            onRunResult={(r) => {
              setRunResult(r); setRunStatus("ready");
              // NARR-CHAT-LOOP: a chat $0 replay carries the case it graded — keep the shared
              // active case in sync so the Case/Report panes show the case the chat just ran.
              if (r && r.case_id) setActiveCase(r.case_id);
            }}
            onConfigSaved={refreshJourney} nextStepName={nextStep(journey)}
            readiness={readiness} />
          {open && !full && (
            <div className="rz" onPointerDown={(e) => drag(e, rightW, setRightW, 340, 680, true)} />
          )}
          {open && (
            <ArtifactPane
              width={rightW} full={full} tab={tab} setTab={setTab} agent={activeAgent}
              wsPack={wsPack}
              activeCase={activeCase} onSelectCase={onSelectCase}
              selectedIds={selectedIds} onToggleSelect={onToggleSelect}
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
