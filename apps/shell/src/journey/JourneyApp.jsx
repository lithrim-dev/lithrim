/* JourneyApp.jsx — composition, phase state, interactions, resizing (ESM port of
   journeyapp.jsx). Theme is lifted to root.jsx (shared with the eval shell) and arrives
   as props; the prototype's ReactDOM.createRoot(...).render(...) is dropped. */
import { useState, useEffect, useRef } from "react";
import { Icon } from "../icons.jsx";
import { Mark } from "../brand.jsx";
import { TopBarJ, LeftRailJ, StatusBarJ, PhaseFoot } from "./chrome.jsx";
import { ACTS } from "./journeyData.js";
import { Center1, Artifact1 } from "./jp1.jsx";
import { Center2, Artifact2 } from "./jp2.jsx";
import { Center3, Artifact3 } from "./jp3.jsx";
import { Center4, Artifact4 } from "./jp4.jsx";

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

const CENTERS = { 1: Center1, 2: Center2, 3: Center3, 4: Center4 };
const ARTIFACTS = { 1: Artifact1, 2: Artifact2, 3: Artifact3, 4: Artifact4 };

const ART_META = {
  1: ["Healthcare pack", "v1.2.0 · installed"],
  2: ["Verification", "scribe-v4 · live"],
  3: ["Calibration", "council · before vs after"],
  4: ["Your evalpack", "scribe-v4 · 84 cases"],
};

export function JourneyApp({ theme, setTheme, mode, setMode }) {
  const [phase, setPhase] = useState(1);
  // Pane defaults match the Shell (app.jsx) so toggling Shell↔Journey doesn't jump.
  const [leftW, setLeftW] = useState(270);
  const [rightW, setRightW] = useState(440);
  const [open, setOpen] = useState(true);
  const [full, setFull] = useState(false);

  const [agent, setAgent] = useState("scribe");
  const [verify, setVerify] = useState("idle");
  const [revealed, setRevealed] = useState(0);
  const [calib, setCalib] = useState("idle");
  const timers = useRef([]);

  // keyboard phase nav
  useEffect(() => {
    const h = (e) => {
      const tag = (e.target.tagName || "").toLowerCase();
      if (tag === "textarea" || tag === "input") return;
      if (e.key === "ArrowRight" && phase < 4) setPhase(phase + 1);
      if (e.key === "ArrowLeft" && phase > 1) setPhase(phase - 1);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [phase]);

  // reset transient hero state when leaving a phase
  useEffect(() => { timers.current.forEach(clearTimeout); timers.current = []; }, [phase]);

  const runVerify = () => {
    setVerify("running"); setRevealed(0);
    timers.current.forEach(clearTimeout); timers.current = [];
    for (let n = 1; n <= 4; n++) timers.current.push(setTimeout(() => setRevealed(n), 600 * n));
    timers.current.push(setTimeout(() => setVerify("done"), 600 * 4 + 500));
  };

  const runCalib = () => {
    setCalib("running");
    timers.current.push(setTimeout(() => setCalib("done"), 1700));
  };

  const drag = (e, base, apply, lo, hi, invert) => {
    e.preventDefault();
    const sx = e.clientX;
    const move = (ev) => apply(clamp(base + (invert ? sx - ev.clientX : ev.clientX - sx), lo, hi));
    const up = () => { document.removeEventListener("pointermove", move); document.removeEventListener("pointerup", up); document.body.classList.remove("resizing"); };
    document.addEventListener("pointermove", move); document.addEventListener("pointerup", up); document.body.classList.add("resizing");
  };

  const Center = CENTERS[phase];
  const Artifact = ARTIFACTS[phase];
  const centerProps = { 1: { agent, setAgent }, 2: { verify, runVerify }, 3: { calib, runCalib }, 4: {} }[phase];
  const artProps = { 1: {}, 2: { verify, revealed }, 3: { calib }, 4: {} }[phase];
  const [artTitle, artSub] = ART_META[phase];

  return (
    <div className="desk">
      <div className="win">
        <TopBarJ theme={theme} setTheme={setTheme} panelOn={open} togglePanel={() => { setOpen((o) => !o); setFull(false); }} phase={phase} mode={mode} setMode={setMode} />
        <div className="body">
          <LeftRailJ width={leftW} phase={phase} setPhase={setPhase} calib={calib} />
          <div className="rz" onPointerDown={(e) => drag(e, leftW, setLeftW, 220, 380)} />

          <main className="center">
            <div className="center-hd">
              <div className="msg" style={{ margin: 0, alignItems: "center", gap: 10 }}>
                <div className="av ai" style={{ marginTop: 0 }}><Mark size={17} /></div>
                <div>
                  <div className="h-title" style={{ lineHeight: 1.1 }}>Journey mode</div>
                  <div className="h-sub">Act {phase} · {ACTS[phase - 1].name}</div>
                </div>
              </div>
              <span className="chip" style={{ marginLeft: "auto" }}><span className="d" style={{ background: "var(--accent)" }} /> guided setup</span>
              {!open && <button className="btn btn-ghost" onClick={() => setOpen(true)}><Icon name="panel" size={15} /> Open {artTitle.toLowerCase()}</button>}
            </div>
            <div className="convo">
              <Center {...centerProps} />
            </div>
            <PhaseFoot phase={phase} setPhase={setPhase} />
          </main>

          {open && !full && <div className="rz" onPointerDown={(e) => drag(e, rightW, setRightW, 340, 680, true)} />}
          {open && (
            <section className={"artifact" + (full ? " full" : "")} style={full ? {} : { width: rightW }}>
              <div className="art-hd">
                <div className="art-toprow">
                  <div style={{ minWidth: 0 }}>
                    <div className="ttl">{artTitle}</div>
                    <div className="sub">{artSub}</div>
                  </div>
                  <div className="right">
                    <button className="btn btn-ghost" style={{ height: 28, padding: "0 10px" }}><Icon name="copy" size={14} /> Export</button>
                    <button className="icon-btn" title={full ? "Exit fullscreen" : "Fullscreen"} onClick={() => setFull((f) => !f)}><Icon name={full ? "minimize" : "expand"} size={16} /></button>
                    <button className="icon-btn" title="Close" onClick={() => { setOpen(false); setFull(false); }}><Icon name="close" size={16} /></button>
                  </div>
                </div>
              </div>
              <div className="art-bd">
                <div style={full ? { maxWidth: 780, margin: "0 auto" } : {}} key={phase}>
                  <Artifact {...artProps} />
                </div>
              </div>
            </section>
          )}
        </div>
        <StatusBarJ phase={phase} calib={calib} />
      </div>
    </div>
  );
}
