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

// The ws5 BFF (uvicorn :8787) — the journey calls the REAL engine through it (grade + case).
// CORS is set for :5180. Replay is $0; the journey falls back to the bundled fixtures if it's down.
const BFF_URL = "http://localhost:8787";

const CENTERS = { 1: Center1, 2: Center2, 3: Center3, 4: Center4 };
const ARTIFACTS = { 1: Artifact1, 2: Artifact2, 3: Artifact3, 4: Artifact4 };

const ART_META = {
  1: ["Healthcare pack", "v1.2.0 · installed"],
  2: ["Verification", "scribe-v4 · recorded run"],
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
  const [calibStep, setCalibStep] = useState(0); // Act 3: how many calibration levers the user has applied
  const [calibBusy, setCalibBusy] = useState(false);
  const [reveal2, setReveal2] = useState(false); // the second beat of a timed reveal (Act 2 reversal)
  const [caseData, setCaseData] = useState(null); // GET /v1/case — the real case the council grades
  const [gradeResult, setGradeResult] = useState(null); // POST /v1/run-eval — the real grade + votes
  const [bffDown, setBffDown] = useState(false); // BFF unreachable → fall back to bundled fixtures
  const timers = useRef([]);
  const convoRef = useRef(null);
  const calib = calibStep >= 2 ? "done" : calibStep > 0 ? "running" : "idle"; // derived, for rail/status chrome

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

  // conversational scroll: a new act starts at the top; a reveal (verdict / floor flip) scrolls
  // the conversation to the latest bot beat so the blind-clicker can't miss the stop moment.
  useEffect(() => { convoRef.current?.scrollTo({ top: 0 }); }, [phase]);

  // fetch the REAL case the council grades when entering Act 2, so the shell displays the same
  // case it scores (no mockup mismatch). Falls back to the bundled EXCHANGE if the BFF is down.
  useEffect(() => {
    if (phase === 2 && !caseData) {
      fetch(`${BFF_URL}/v1/case?agent=ws0_default`)
        .then((r) => (r.ok ? r.json() : null))
        .then((c) => { if (c) setCaseData(c); })
        .catch(() => {});
    }
  }, [phase, caseData]);
  useEffect(() => {
    if (verify === "done" || reveal2 || calibStep > 0) {
      const c = convoRef.current;
      const id = setTimeout(() => { if (c) c.scrollTop = c.scrollHeight; }, 160);
      return () => clearTimeout(id);
    }
  }, [verify, reveal2, calibStep]);

  const runVerify = async (opts = {}) => { // calls the real council via the BFF; opts.live => a fresh paid in-process run
    const inProcess = !!opts.live;
    setVerify("running"); setRevealed(0); setReveal2(false); setGradeResult(null);
    timers.current.forEach(clearTimeout); timers.current = [];
    for (let n = 1; n <= 3; n++) timers.current.push(setTimeout(() => setRevealed(n), 650 * n)); // poll anim
    let rec = null;
    try {
      const res = await fetch(`${BFF_URL}/v1/run-eval`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent: "ws0_default", live: false, in_process: inProcess }),
      });
      if (res.ok) rec = await res.json();
    } catch { /* BFF unreachable → fall back to the bundled fixture */ }
    setBffDown(!rec);
    setGradeResult(rec);
    setRevealed(3);
    setVerify("done");
    timers.current.push(setTimeout(() => setReveal2(true), 1300));
  };

  const runCalibStep = () => { // the user applies one calibration lever + re-runs; precision climbs
    if (calibBusy || calibStep >= 2) return;
    setCalibBusy(true);
    timers.current.push(setTimeout(() => { setCalibStep((s) => s + 1); setCalibBusy(false); }, 1200));
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
  const centerProps = { 1: { agent, setAgent }, 2: { verify, runVerify, reveal2, gradeResult, caseData, bffDown }, 3: { calibStep, calibBusy, runCalibStep }, 4: {} }[phase];
  const artProps = { 1: {}, 2: { verify, revealed, gradeResult, caseData }, 3: { calibStep }, 4: {} }[phase];
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
            <div className="convo" ref={convoRef}>
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
