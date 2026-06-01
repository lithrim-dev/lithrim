/* app.jsx — shell composition, resizable panes, theme, status bar (ported verbatim). */
import { useState, useEffect } from "react";
import { Icon as I } from "./icons.jsx";
import { LeftRail, CenterPane } from "./panes.jsx";
import { ArtifactPane } from "./artifact.jsx";

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

function TopBar({ theme, setTheme, artifactOpen, toggleArtifact }) {
  return (
    <div className="titlebar">
      <div className="lights"><span className="light r" /><span className="light y" /><span className="light g" /></div>
      <div className="tb-crumb">
        <span className="ws-pill"><span className="dot" /> acme-support</span>
        <span className="crumb-sep"><I name="chevR" size={14} /></span>
        <span className="crumb-txt">Evaluations <span className="crumb-sep">/</span> <b>Support Agent v4</b></span>
      </div>

      <div className="tb-cmd"><I name="search" size={14} /><span>Search or run a command…</span><span className="kbd">⌘K</span></div>

      <div className="tb-right">
        <button className="icon-btn" title="Toggle theme" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>
          <I name={theme === "light" ? "moon" : "sun"} size={16} />
        </button>
        <button className={"icon-btn" + (artifactOpen ? " on" : "")} title="Toggle artifact panel" onClick={toggleArtifact}>
          <I name="panel" size={16} />
        </button>
        <button className="btn btn-primary"><I name="bolt" size={14} /> Run eval</button>
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

function App() {
  const [leftW, setLeftW] = useState(270);
  const [rightW, setRightW] = useState(440);
  const [open, setOpen] = useState(true);
  const [full, setFull] = useState(false);
  const [tab, setTab] = useState("report");
  const [theme, setTheme] = useState("light");
  const [active, setActive] = useState("t1");

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
          toggleArtifact={() => { setOpen((o) => !o); setFull(false); }} />
        <div className="body">
          <LeftRail width={leftW} active={active} setActive={setActive} />
          <div className="rz" onPointerDown={(e) => drag(e, leftW, setLeftW, 220, 380)} />
          <CenterPane onOpenArtifact={openArtifact} artifactOpen={open} />
          {open && !full && (
            <div className="rz" onPointerDown={(e) => drag(e, rightW, setRightW, 340, 680, true)} />
          )}
          {open && (
            <ArtifactPane
              width={rightW} full={full} tab={tab} setTab={setTab}
              onClose={() => { setOpen(false); setFull(false); }}
              onToggleFull={() => setFull((f) => !f)}
            />
          )}
        </div>
        <StatusBar />
      </div>
    </div>
  );
}

export default App;
