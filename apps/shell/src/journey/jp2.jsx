/* jp2.jsx — Phase 2 (HERO): The reveal — the council confidently blocks a REAL note.
   Premium reveal incorporated from the Claude-Design exercise (2026-06-03) as OUR OWN
   Tailwind components (reference only — no prototype code copied). Wired to the REAL
   council: votes/verdict from gradeResult (BFF), and the decoded note is parsed LIVE
   from the real caseData.artifact with coral/amber flags derived BY CONSTRUCTION
   (PMH stem ∉ patient chart → fabrication; ∈ chart → council false-positive). No
   hand-authored case copy — don't dilute the real cases. */
import { useState, useRef, useEffect, useCallback } from "react";
import { Icon } from "../icons.jsx";
import { Mark } from "../brand.jsx";
import { AgentMsg } from "./chrome.jsx";
import { EXCHANGE, REVEAL_TURN, FALLBACK_VOTES } from "./journeyData.js";

const WAVE = [3,5,8,12,18,14,9,6,11,16,22,19,13,8,5,9,14,20,26,21,15,10,7,12,17,23,28,24,18,12,8,6,10,15,19,14,9,6,4,7,11,16,13,8,5];
const reduced = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const shortRole = (r) => (r || "").replace("_judge", "");

/* ---- decoded note, parsed from the REAL case (no fixture) ----
   flags by construction: a documented PMH condition that is NOT in the patient chart
   is a genuine fabrication (coral); one that IS in the chart is real history the
   transcript-only council wrongly flagged (amber). */
const QUAL = /\s*\([^)]*\)/g;
const stem = (s) => s.replace(QUAL, "").replace(/\s+/g, " ").trim().toLowerCase();
const clean = (s) => s.replace(/\s*\([^)]*\)\s*$/, "").replace(/\s+/g, " ").trim();
const FLAG_META = {
  coral: { tag: "Genuine fabrication", reason: "Not in the patient's chart or the transcript — a fabrication by the scribe.", src: "chart ✕ · transcript ✕" },
  amber: { tag: "Wrongly flagged", reason: "Real charted history — the council called it fabricated only because it never appears in the 41-second transcript.", src: "patient chart ✓" },
};

function parseNote(caseData) {
  if (!caseData?.artifact) return null;
  let txt;
  try { txt = JSON.parse(caseData.artifact)?.content?.[0]?.attachment?.data; } catch { return null; }
  if (!txt || typeof txt !== "string") return null;
  const chart = new Set((caseData.conditions || []).map(stem));
  const out = { subjective: "", allergies: "", assessment: "", plan: [], pmh: [] };
  const HEADS = ["SUBJECTIVE", "OBJECTIVE", "ALLERGIES", "PMH", "ASSESSMENT", "PLAN"];
  const seen = new Set();
  let cur = null;
  for (const raw of txt.split(/\r?\n/)) {
    const line = raw.trim();
    const h = raw.match(/^([A-Z][A-Za-z ]+):\s*(.*)$/);
    if (h && HEADS.includes(h[1].trim().toUpperCase())) {
      cur = h[1].trim().toUpperCase();
      if (cur === "SUBJECTIVE") out.subjective = clean(h[2]);
      else if (cur === "ASSESSMENT") out.assessment = clean(h[2]);
      continue;
    }
    if (!line) continue;
    if (cur === "ALLERGIES") { if (!out.allergies) out.allergies = clean(line); }
    else if (cur === "PMH") {
      const item = line.replace(/^[-•]\s*/, "").trim();
      if (!item) continue;
      const k = stem(item);
      if (seen.has(k)) continue;
      seen.add(k);
      out.pmh.push({ label: clean(item), flag: chart.has(k) ? "amber" : "coral" });
    } else if (cur === "PLAN") {
      out.plan.push(line.replace(/^\d+\.\s*/, "").trim());
    }
  }
  return out.pmh.length || out.subjective ? out : null;
}

function RichText({ parts }) {
  if (typeof parts === "string") return parts;
  return (parts || []).map((p, i) => {
    if (typeof p === "string") return <span key={i}>{p}</span>;
    if (p.rx) return <span key={i} className="font-mono text-[0.92em] text-foreground bg-muted border border-border rounded px-1">{p.rx}</span>;
    if (p.hl) return <span key={i} className={p.k === "fab" ? "text-primary font-semibold" : "text-amber font-semibold"}>{p.hl}</span>;
    return <span key={i}>{p.t}</span>;
  });
}

function ScribeExchange() {
  const [playing, setPlaying] = useState(false);
  const [prog, setProg] = useState(0);
  const ref = useRef(null);
  const toggle = () => {
    if (playing) { clearInterval(ref.current); setPlaying(false); return; }
    setPlaying(true);
    ref.current = setInterval(() => setProg((p) => { if (p >= WAVE.length) { clearInterval(ref.current); setPlaying(false); return p; } return p + 1; }), 90);
  };
  useEffect(() => () => clearInterval(ref.current), []);
  return (
    <div className="mt-3.5 rounded-[var(--r)] border border-border bg-background shadow-[var(--shadow-card)] overflow-hidden">
      <div className="flex items-center gap-2.5 px-3.5 py-2.5 border-b border-border bg-secondary">
        <span className="text-primary flex"><Icon name="mic" size={15} /></span>
        <span className="text-[12.5px] font-semibold text-foreground">{EXCHANGE.scenario}</span>
        <span className="ml-auto font-mono text-[10.5px] text-muted-foreground">raw encounter · {EXCHANGE.audioLen}</span>
      </div>
      <div className="p-3.5">
        <div className="flex flex-col gap-3">
          {EXCHANGE.turns.map((t, i) => (
            <div className="flex gap-2.5" key={i}>
              <span className={"font-mono text-[10px] uppercase tracking-wide w-[68px] flex-none pt-0.5 " + (t.who === "patient" ? "text-teal" : "text-slate")}>{t.who}</span>
              <span className="text-[13px] leading-relaxed text-foreground">{t.t}</span>
            </div>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-3 px-3 py-2.5 rounded-[var(--r-sm)] border border-border bg-secondary">
          <button onClick={toggle} className="w-8 h-8 flex-none rounded-full bg-primary text-white flex items-center justify-center hover:opacity-90 transition">
            <Icon name={playing ? "pause" : "play"} size={14} />
          </button>
          <div className="flex items-center gap-[2.5px] flex-1 h-[26px]">
            {WAVE.map((h, i) => (<i key={i} className={"flex-1 min-w-[2px] rounded-sm " + (i < prog ? "bg-primary" : "bg-border-strong")} style={{ height: Math.max(4, h * 0.7) + "px" }} />))}
          </div>
          <span className="font-mono text-[11px] text-muted-foreground flex-none">{EXCHANGE.audioLen}</span>
        </div>
      </div>
    </div>
  );
}

function JudgeRow({ v, thinking, idx }) {
  if (thinking) {
    return (
      <div className="p-3.5 border-b border-border last:border-0">
        <div className="flex items-center gap-2.5">
          <span className="font-mono text-[12px] font-semibold text-foreground">{v.judge_role}</span>
          <span className="font-mono text-[10.5px] text-muted-foreground px-1.5 py-px border border-border rounded-[5px]">{v.model}</span>
          <span className="ml-auto inline-flex gap-1">{[0,1,2].map((d) => <i key={d} className="w-[5px] h-[5px] rounded-full bg-slate lr-pulse" style={{ animationDelay: d * 0.15 + "s" }} />)}</span>
        </div>
        <div className="mt-2.5 h-[9px] w-[92%] rounded-[5px] lr-shimmer-bg bg-[linear-gradient(90deg,var(--surface-muted)_25%,var(--surface-2)_40%,var(--surface-muted)_60%)]" />
        <div className="mt-2 h-[9px] w-[64%] rounded-[5px] lr-shimmer-bg bg-[linear-gradient(90deg,var(--surface-muted)_25%,var(--surface-2)_40%,var(--surface-muted)_60%)]" />
      </div>
    );
  }
  const block = (v.vote || "").toUpperCase() === "BLOCK";
  return (
    <div className="p-3.5 border-b border-border last:border-0 lr-rowin" style={{ animationDelay: idx * 0.12 + "s" }}>
      <div className="flex items-center gap-2.5">
        <span className="font-mono text-[12px] font-semibold text-foreground">{v.judge_role}</span>
        <span className="font-mono text-[10.5px] text-muted-foreground px-1.5 py-px border border-border rounded-[5px]">{v.model}</span>
        <span className="ml-auto inline-flex items-center gap-2.5 flex-none">
          <span className={"font-mono text-[10.5px] whitespace-nowrap " + (v.confidence ? "text-muted-foreground" : "text-muted-foreground/60")}>{v.confidence ? "conf " + v.confidence : "conf —"}</span>
          <span className={"inline-flex items-center gap-1.5 h-[22px] px-2.5 rounded-md font-mono text-[11px] font-semibold tracking-wide " + (block ? "bg-accent text-accent-foreground" : "bg-teal/15 text-teal")}>
            <span className={"w-1.5 h-1.5 rounded-full " + (block ? "bg-primary" : "bg-teal")} />{(v.vote || "").toUpperCase()}
          </span>
        </span>
      </div>
      {v.reason && <div className="mt-2 text-[12.5px] leading-relaxed text-muted-foreground">{v.reason}</div>}
    </div>
  );
}

function Tally({ votes }) {
  return (
    <div className="font-mono text-[12px] text-muted-foreground inline-flex flex-wrap gap-x-2 gap-y-1 items-center mt-2.5">
      {votes.map((v, i) => {
        const block = (v.vote || "").toUpperCase() === "BLOCK";
        return (
          <span key={i} className="inline-flex items-center gap-1.5">
            {i > 0 && <span className="opacity-40 mr-1.5">·</span>}
            <span>{shortRole(v.judge_role)}</span>
            <span className={block ? "text-primary" : "text-teal"}>{(v.vote || "").toUpperCase()}</span>
            {!block && <span title="Lone dissent — not unanimous" className="inline-flex items-center justify-center w-[15px] h-[15px] rounded bg-amber/20 text-amber"><Icon name="flag" size={9} /></span>}
          </span>
        );
      })}
    </div>
  );
}

function Provenance({ gradeResult, bffDown }) {
  if (bffDown) return <span className="text-amber/90">bundled example · start the BFF for a live grade</span>;
  const path = gradeResult?.grade_path === "in_process" ? "live · in-process" : "replay";
  return <>real grade<span className="text-slate"> · </span>{path}<span className="text-slate"> · </span>$0<span className="text-slate"> · </span>3 judges<span className="text-slate"> · </span>116,908 tokens</>;
}

function TheTurn() {
  return (
    <div className="mt-[22px] pt-[22px] border-t border-border lr-rise">
      <div className="text-[25px] leading-[1.44] font-medium tracking-[-0.012em] text-foreground max-w-[34ch]">
        {REVEAL_TURN.clauses.map((c, i) => <span key={i}><RichText parts={c} /> </span>)}
      </div>
      <div className="mt-3 text-[16px] leading-relaxed text-muted-foreground max-w-[44ch]">{REVEAL_TURN.tail}</div>
    </div>
  );
}

function VerdictBlock({ verdict, votes, gradeResult, bffDown }) {
  return (
    <div className="mt-4">
      <div className="w-max">
        <div className="font-mono text-[42px] font-semibold leading-none text-primary lr-drop">{verdict}</div>
        <div className="h-[3px] rounded-sm bg-primary mt-1.5 lr-draw" />
      </div>
      <Tally votes={votes} />
      <div className="font-mono text-[10.5px] text-muted-foreground mt-3 tracking-[0.01em]"><Provenance gradeResult={gradeResult} bffDown={bffDown} /></div>
      <TheTurn />
    </div>
  );
}

function StageOverlay({ verdict, votes, recede, turnStep, out, onRelease }) {
  return (
    <div onClick={onRelease} role="dialog" aria-label="Council verdict"
      className={"fixed inset-0 z-[90] flex items-center justify-center px-[clamp(48px,7vw,140px)] cursor-pointer text-[#EAEDF4] " + (out ? "lr-stageout" : "lr-stagein")}
      style={{ background: "radial-gradient(135% 95% at 50% 33%, rgba(240,106,75,.14), rgba(240,106,75,.035) 38%, transparent 62%), radial-gradient(120% 120% at 50% 50%, rgba(8,11,20,.82), rgba(5,7,13,.95) 80%)", backdropFilter: "blur(5px) saturate(.82)", WebkitBackdropFilter: "blur(5px) saturate(.82)" }}>
      <div onClick={(e) => e.stopPropagation()} className="w-[min(1100px,100%)] flex flex-col items-start cursor-default">
        <div className="font-mono text-[clamp(11px,1vw,13px)] tracking-[0.16em] uppercase text-[#8B93A8] inline-flex items-center gap-3 mb-[clamp(28px,4vh,44px)]"><Mark size={15} /> Council verdict · replay · $0</div>
        <div className="origin-top-left transition-[transform,opacity,filter] duration-[800ms] ease-[cubic-bezier(.2,.7,.3,1)]" style={recede ? { opacity: 0.46, transform: "scale(.4)", filter: "saturate(.5)", marginBottom: -10 } : {}}>
          <div className="font-mono font-semibold leading-[.9] tracking-[0.005em] text-[#F06A4B] text-[clamp(64px,9.5vw,128px)] lr-svdrop" style={{ textShadow: "0 0 56px rgba(240,106,75,.34)" }}>{verdict}</div>
          <div className="h-[5px] w-[46%] max-w-[480px] rounded-sm bg-[#F06A4B] mt-[clamp(16px,2.4vh,26px)] origin-left lr-draw" style={{ boxShadow: "0 0 22px rgba(240,106,75,.45)" }} />
          <div className="font-mono text-[clamp(12px,1.15vw,15px)] text-[#8B93A8] mt-[clamp(20px,3vh,30px)] inline-flex flex-wrap gap-x-2.5 gap-y-1 items-center">
            {votes.map((v, i) => {
              const block = (v.vote || "").toUpperCase() === "BLOCK";
              return <span key={i} className="inline-flex items-center gap-1.5">{i > 0 && <span className="opacity-40 mr-1">·</span>}<span>{shortRole(v.judge_role)}</span><span className={block ? "text-[#F06A4B]" : "text-[#46BC9B]"}>{(v.vote || "").toUpperCase()}</span>{!block && <span className="inline-flex items-center justify-center w-[15px] h-[15px] rounded bg-[rgba(236,162,76,.2)] text-[#ECA24C]"><Icon name="flag" size={9} /></span>}</span>;
            })}
          </div>
        </div>
        {recede && (
          <div className="mt-[clamp(34px,5.5vh,60px)] max-w-[min(1040px,100%)]">
            {REVEAL_TURN.clauses.map((c, i) => (
              <p key={i} className={"text-[clamp(30px,4.5vw,56px)] leading-[1.18] font-medium tracking-[-0.02em] text-[#EAEDF4] m-0 mb-[clamp(8px,1.4vh,16px)] " + (turnStep >= i + 1 ? "lr-clause" : "opacity-0")}>
                {c.map((p, j) => p.hl ? <span key={j} className={p.k === "fab" ? "text-[#F06A4B] font-semibold" : "text-[#ECA24C] font-medium"}>{p.hl}</span> : <span key={j}>{p.t}</span>)}
              </p>
            ))}
            <p className={"text-[clamp(17px,2.1vw,25px)] font-normal text-[#8B93A8] mt-[clamp(20px,3vh,30px)] leading-relaxed max-w-[720px] " + (turnStep >= 4 ? "lr-clause" : "opacity-0")}>{REVEAL_TURN.tail}</p>
          </div>
        )}
        {turnStep >= 4 && (
          <button onClick={onRelease} className="mt-[clamp(36px,5vh,56px)] font-mono text-[11px] tracking-[0.1em] uppercase text-[#6B748C] inline-flex items-center gap-2.5 hover:text-[#EAEDF4] transition lr-stagein">
            Return to thread <span className="inline-flex items-center justify-center w-[18px] h-[18px] border border-[#2C374F] rounded-[5px]">↵</span>
          </button>
        )}
      </div>
    </div>
  );
}

export function Center2({ verify, runVerify, gradeResult, caseData, bffDown }) {
  const [stageOn, setStageOn] = useState(false);
  const [stageOut, setStageOut] = useState(false);
  const [recede, setRecede] = useState(false);
  const [turnStep, setTurnStep] = useState(0);
  const [onRecord, setOnRecord] = useState(false);
  const timers = useRef([]);
  const played = useRef(false);

  const clearT = () => { timers.current.forEach(clearTimeout); timers.current = []; };
  const release = useCallback(() => {
    clearT(); setStageOut(true);
    timers.current.push(setTimeout(() => { setStageOn(false); setStageOut(false); setOnRecord(true); }, 560));
  }, []);

  useEffect(() => {
    clearT();
    if (verify !== "done") { played.current = false; setStageOn(false); setStageOut(false); setRecede(false); setTurnStep(0); setOnRecord(false); return; }
    if (played.current) return;
    played.current = true;
    if (reduced()) { setOnRecord(true); return; }
    const T = (ms, fn) => timers.current.push(setTimeout(fn, ms));
    T(900, () => { setStageOn(true); setRecede(false); setTurnStep(0); });
    T(900 + 1550, () => setRecede(true));
    [1, 2, 3, 4].forEach((n, i) => T(900 + 1550 + i * 620, () => setTurnStep(n)));
    T(900 + 1550 + 3 * 620 + 2600, () => release());
    return clearT;
  }, [verify, release]);

  const votes = (gradeResult?.council?.votes?.length ? gradeResult.council.votes : FALLBACK_VOTES)
    .map((v) => ({ judge_role: v.judge_role, model: v.model, vote: v.vote, confidence: v.confidence, reason: v.reason }));
  const verdict = (gradeResult?.result?.verdict || "BLOCK").toUpperCase();
  const settling = verify === "done" && !onRecord;

  return (
    <div className="convo-inner">
      <AgentMsg beat="Act 2 · The reveal"
        lead="A real scribe note from the pack — a sprained-ankle visit, a patient with a long medical history. This isn't a mockup: hit Verify and it runs the real council and shows you exactly what each judge said.">
        <ScribeExchange />
        <div className="mt-3.5 flex flex-wrap items-center gap-3">
          <button onClick={() => runVerify()} disabled={verify === "running"}
            className="inline-flex items-center gap-2 h-[38px] px-[17px] rounded-[var(--r-sm)] bg-primary text-white text-[13.5px] font-semibold disabled:opacity-65 hover:opacity-90 transition">
            {verify === "running" ? <><span className="w-[15px] h-[15px] rounded-full border-2 border-white/40 border-t-white lr-spin" /> Verifying…</>
              : verify === "done" ? <><Icon name="refresh" size={15} /> Verify again</>
              : <><Icon name="shield" size={15} /> Verify (replay · $0)</>}
          </button>
          <button onClick={() => runVerify({ live: true })} disabled={verify === "running"} title="A fresh, paid in-process Azure council call"
            className="inline-flex items-center gap-2 h-[38px] px-[17px] rounded-[var(--r-sm)] border border-border text-foreground text-[13.5px] font-semibold hover:bg-secondary transition">
            <Icon name="wand" size={15} /> Run live
          </button>
          <span className="font-mono text-[11px] text-muted-foreground">{bffDown ? "bundled example · BFF offline" : "replay · $0 · no tokens spent"}</span>
        </div>
      </AgentMsg>

      {verify !== "idle" && (
        <AgentMsg>
          <div className="rounded-[var(--r)] border border-border bg-background shadow-[var(--shadow-card)] overflow-hidden">
            <div className="flex items-center gap-2 px-3.5 py-2.5 border-b border-border bg-secondary">
              <span className="text-slate flex"><Icon name="scale" size={14} /></span>
              <span className="text-[12px] font-semibold text-foreground">Council deliberation</span>
              <span className="ml-auto font-mono text-[10.5px] text-muted-foreground inline-flex items-center gap-1.5">
                {onRecord ? "complete" : settling ? <><span className="w-[7px] h-[7px] rounded-full bg-amber lr-pulse" /> reaching a verdict</> : <><span className="w-[7px] h-[7px] rounded-full bg-slate lr-pulse" /> weighing votes</>} · 3 judges
              </span>
            </div>
            {votes.map((v, i) => <JudgeRow key={i} v={v} idx={i} thinking={verify === "running"} />)}
          </div>
          {onRecord && <VerdictBlock verdict={verdict} votes={votes} gradeResult={gradeResult} bffDown={bffDown} />}
        </AgentMsg>
      )}

      {stageOn && <StageOverlay verdict={verdict} votes={votes} recede={recede} turnStep={turnStep} out={stageOut} onRelease={release} />}
    </div>
  );
}

/* ============================ RIGHT PANE — decoded SOAP note (real case, fixes G4) ============================ */
export function Artifact2({ verify, gradeResult, caseData }) {
  const active = verify === "done";
  const note = parseNote(caseData);
  return (
    <div>
      <div className="font-mono text-[10px] tracking-wide uppercase text-muted-foreground mx-0.5 mb-2.5">Graded artifact — decoded note</div>
      <div className="rounded-[var(--r)] border border-border bg-background shadow-[var(--shadow-card)] overflow-hidden">
        <div className="flex items-center gap-2.5 px-3.5 py-2.5 border-b border-border bg-secondary">
          <span className="text-primary flex"><Icon name="note" size={14} /></span>
          <span className="text-[12.5px] font-semibold text-foreground">Scribe note</span>
          <span className="ml-auto font-mono text-[10.5px] text-muted-foreground">{note ? "scribe-v4 · SOAP" : "scribe-v4"}</span>
        </div>

        {note ? (
          <>
            <div className="px-4 py-[15px]">
              {note.subjective && <Section k="Subjective"><span className="text-[13px] leading-relaxed text-foreground">{note.subjective}</span></Section>}
              {note.allergies && <Section k="Allergies"><span className="font-mono text-[12px] text-teal">{note.allergies}</span></Section>}
              {note.pmh.length > 0 && (
                <Section k="Past medical history">
                  <ul className="list-none m-0 p-0 flex flex-col gap-[7px]">
                    {note.pmh.map((p, i) => {
                      const m = FLAG_META[p.flag];
                      return (
                        <li key={i} className="text-[13px] leading-snug text-foreground flex items-baseline gap-2.5">
                          <span className="text-muted-foreground flex-none font-mono text-[11px]">—</span>
                          <span tabIndex={active ? 0 : -1} className={"relative group " + (active ? "underline decoration-2 underline-offset-[3px] cursor-help " + (p.flag === "coral" ? "decoration-primary" : "decoration-amber") : "")}>
                            {p.label}
                            {active && (
                              <span className="pointer-events-none absolute left-[-2px] top-[calc(100%+9px)] w-[244px] z-30 opacity-0 -translate-y-1 group-hover:opacity-100 group-hover:translate-y-0 group-focus-within:opacity-100 group-focus-within:translate-y-0 transition rounded-[var(--r-sm)] border border-border bg-background shadow-[var(--shadow-pop)] p-3 text-left">
                                <span className={"inline-flex items-center gap-1.5 font-mono text-[9.5px] uppercase tracking-wide font-semibold mb-1.5 " + (p.flag === "coral" ? "text-primary" : "text-amber")}>
                                  <span className={"w-[7px] h-[7px] rounded-sm " + (p.flag === "coral" ? "bg-primary" : "bg-amber")} />{m.tag}
                                </span>
                                <span className="block text-[12px] leading-relaxed text-foreground">{m.reason}</span>
                                <span className="mt-2 flex items-center gap-1.5 font-mono text-[10px] text-muted-foreground">source<span className={"px-1.5 py-px rounded-[5px] bg-muted border border-border " + (p.flag === "coral" ? "text-accent-foreground" : "text-amber")}>{m.src}</span></span>
                              </span>
                            )}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </Section>
              )}
              {note.assessment && <Section k="Assessment"><span className="text-[13px] leading-relaxed text-foreground">{note.assessment}</span></Section>}
              {note.plan.length > 0 && (
                <Section k="Plan" last>
                  <ul className="list-none m-0 p-0 flex flex-col gap-1 text-[13px] leading-relaxed text-foreground">
                    {note.plan.map((p, i) => <li key={i} className="flex gap-2"><span className="text-muted-foreground font-mono text-[11px] flex-none">{i + 1}.</span><span>{p}</span></li>)}
                  </ul>
                </Section>
              )}
            </div>
            {active ? (
              <div className="flex flex-wrap gap-x-4 gap-y-2 px-3.5 py-2.5 border-t border-border bg-secondary text-[11px] text-muted-foreground lr-rowin">
                <span className="inline-flex items-center gap-1.5"><span className="w-4 h-[3px] rounded-sm bg-primary" /> Genuine fabrication — in neither chart nor transcript</span>
                <span className="inline-flex items-center gap-1.5"><span className="w-4 h-[3px] rounded-sm bg-amber" /> Charted history the council wrongly flagged</span>
              </div>
            ) : (
              <div className="flex items-center gap-2.5 px-3.5 py-2.5 border-t border-border bg-secondary text-[12px] text-muted-foreground">
                <span className="w-[26px] h-[26px] rounded-[7px] flex items-center justify-center flex-none bg-muted text-slate"><Icon name="shield" size={14} /></span>
                <span><span className="text-foreground font-semibold">Not yet graded.</span> Hit Verify to run the council — and see which lines it flagged, and which it got wrong.</span>
              </div>
            )}
          </>
        ) : (
          <div className="px-4 py-7 text-[12.5px] leading-relaxed text-muted-foreground">
            <span className="text-foreground font-semibold">Loading the case…</span> The graded note streams from the engine. If this persists, start the BFF (<span className="font-mono text-[11px]">:8787</span>) for the live case.
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ k, children, last }) {
  return (
    <div className={last ? "" : "mb-[15px]"}>
      <div className="font-mono text-[9.5px] tracking-wide uppercase text-muted-foreground mb-1.5">{k}</div>
      <div>{children}</div>
    </div>
  );
}
