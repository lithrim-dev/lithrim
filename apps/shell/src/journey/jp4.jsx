/* jp4.jsx — Phase 4: Own it — your real session (audio), fresh scores, validation contract, 8-link audit chain. */
import { Icon } from "../icons.jsx";
import { AgentMsg } from "./chrome.jsx";
import { SESSION, SCORES, CONTRACT, AUDIT_CHAIN, SDK_LINES, PRO_FEATURES } from "./journeyData.js";

export function Center4() {
  return (
    <div className="convo-inner">
      <AgentMsg beat="Act 4 · Own it"
        lead="You calibrated the judges against known truth — they're yours now. So point them at your agent: stream its real conversations in through the SDK. The council you tuned scores every one, and the floor overrules it when it's wrong.">
        <div className="icard" style={{ marginTop: 12, overflow: "hidden" }}>
          <div className="sdk-block" style={{ border: "none", borderRadius: 0 }}>
            <div className="sb-hd"><Icon name="link" size={13} style={{ color: "#8590A8" }} /><span className="fn">capture.ts</span></div>
            <div className="sdk-code">
              {SDK_LINES.map((l, i) => (<div key={i}>{l.length === 1 && l[0][1] === "" ? " " : l.map((p, j) => <span key={j} className={p[0]}>{p[1]}</span>)}</div>))}
            </div>
          </div>
        </div>
        <p className="muted" style={{ marginTop: 10 }}>Your agent — support replies, code, RAG answers, scribe notes — your judges, your floors, your data. Nothing leaves the box: BYOK, local, airgapped.</p>
      </AgentMsg>

      <AgentMsg lead="Here's one session that came through your stream.">
        <p className="muted">The council you built scored it <b>BLOCK · WRONG_DOSAGE</b>; the floor caught the dose drift the judges rationalized away — and every verdict traces back to its source.</p>
        <div className="icard" style={{ marginTop: 12 }}>
          <div className="icard-hd">
            <span className="ic"><Icon name="mic" size={15} /></span>
            <span className="ttl">{SESSION.label}</span>
            <span className="sub">{SESSION.audioLen} · audio + transcript + note</span>
          </div>
          <div className="icard-bd" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {SESSION.audioSrc && <audio controls preload="metadata" src={SESSION.audioSrc} style={{ width: "100%", height: 38 }} />}
            <div className="kb-row"><span className="kb-ic"><Icon name="shield" size={15} /></span><span className="kb-name">Verdict · {SESSION.verdict}</span><span className="kb-meta">{SESSION.finding}</span></div>
          </div>
        </div>
        <p className="muted" style={{ marginTop: 10 }}>Open its <b>8-link audit chain</b> in the panel — verdict → finding → citation → artifact span → transcript turn → the audio moment. The audit a regulator, or a court, actually needs.</p>
      </AgentMsg>

      <AgentMsg lead="Now build your evalpack — from your own traffic, not a vendor's benchmark.">
        <p className="muted">Promote the clean sessions into a <b>golden set</b> (the bar your agent must hold) and the catches into a <b>regression suite</b> (failures that must never ship again).</p>
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 9 }}>
          <div className="promote-row">
            <span className="pr-check"><Icon name="star" size={13} /></span>
            <div style={{ minWidth: 0 }}><div className="pr-n">Golden cases</div><div className="pr-d">Sessions your agent nailed — grounded, traceable, the bar to hold.</div></div>
            <span className="pr-count">24</span>
          </div>
          <div className="promote-row">
            <span className="pr-check" style={{ background: "var(--accent)" }}><Icon name="shield" size={13} /></span>
            <div style={{ minWidth: 0 }}><div className="pr-n">Regression suite</div><div className="pr-d">Drifts &amp; fabrications your council caught — must never ship again.</div></div>
            <span className="pr-count">60</span>
          </div>
        </div>
      </AgentMsg>

      <AgentMsg lead="That's what you own: a calibrated, tool-grounded eval — plus a regression suite that holds the line as your agent changes.">
        <p className="muted">Not a vibe-check. An eval you can defend — to your team, your customers, a regulator. Scale it:</p>
        <div className="icard" style={{ marginTop: 12, border: "none", boxShadow: "none" }}>
          <div className="pro-panel">
            <div className="pro-hd"><span className="pro-badge">Pro</span><span className="pro-t">Take the council further</span></div>
            {PRO_FEATURES.map((f) => (
              <div className="pro-feat" key={f.t}>
                <span className="pf-ic"><Icon name={f.icon} size={15} /></span>
                <div><div className="pf-t">{f.t}</div><div className="pf-d">{f.d}</div></div>
              </div>
            ))}
            <div className="pro-cta"><button className="btn btn-primary btn-lg" style={{ width: "100%", justifyContent: "center" }}><Icon name="lock" size={15} /> Unlock Pro</button></div>
          </div>
        </div>
      </AgentMsg>
    </div>
  );
}

export function Artifact4() {
  return (
    <div>
      <div className="evp-hero">
        <div className="evp-ic"><Icon name="mic" size={22} /></div>
        <div style={{ minWidth: 0 }}>
          <div className="ph-name">{SESSION.id}</div>
          <div className="ph-ver">audio + artifact + transcript · {SESSION.audioLen}</div>
        </div>
        <div className="ph-status"><span className="tag fail"><Icon name="shield" size={11} /> {SESSION.verdict}</span></div>
      </div>

      <div className="art-sec">
        <div className="art-h2">Council scores <span className="cnt">live run · v2 trio</span></div>
        {SCORES.map((s) => (
          <div className="pillar-badge in" key={s.judge} style={{ display: "flex" }}>
            <span className="pb-ic" style={{ background: "var(--accent)" }}><Icon name="shield" size={16} /></span>
            <div style={{ minWidth: 0 }}>
              <div className="pb-name">{s.judge}</div>
              <div className="pb-desc">{s.model} · {s.findings.join(" · ")}</div>
            </div>
            <div className="pb-score"><span className="tag fail">{s.vote}</span><span className="of" style={{ marginLeft: 6 }}>conf {s.conf}</span></div>
          </div>
        ))}
      </div>

      <div className="art-sec">
        <div className="art-h2">By-construction check <span className="cnt">{CONTRACT.name} · {CONTRACT.type}</span></div>
        <p className="muted" style={{ marginBottom: 8 }}>{CONTRACT.rule}</p>
        <div className="cmp-table">
          <div className="cmp-head">{CONTRACT.cols.map((c) => <span key={c}>{c}</span>)}</div>
          {CONTRACT.rows.map((r) => (
            <div className="cmp-row" key={r.variant}>
              <span className="cr-name">{r.variant}</span>
              <span className={"cmp-v " + (r.council === "PASS" ? "pass" : "fail")}>{r.council}</span>
              <span className="cmp-v" style={{ fontFamily: "var(--mono)", fontSize: 10.5 }}>{r.evidence}</span>
              <span className={"cmp-tag " + (r.ok ? "same" : "regressed")}>{r.floor}</span>
            </div>
          ))}
        </div>
        <p className="muted" style={{ marginTop: 8 }}>{CONTRACT.miss} <b>Not the LLM</b> — <span style={{ fontFamily: "var(--mono)", fontSize: 11 }}>dosage_grounding</span> runs in the harness floor, offline.</p>
      </div>

      <div className="art-sec">
        <div className="art-h2">8-link audit chain <span className="cnt">{SESSION.finding} → source</span></div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          {AUDIT_CHAIN.map((c, i) => (
            <div key={c.n} style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "8px 0", borderTop: i ? "1px solid var(--border)" : "none" }}>
              <span style={{ flexShrink: 0, width: 22, height: 22, borderRadius: 11, background: c.kind === "verdict" ? "var(--accent)" : "#eef1f6", color: c.kind === "verdict" ? "#fff" : "var(--muted)", fontSize: 11, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center" }}>{c.n}</span>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 10.5, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: ".05em" }}>{c.link}{c.kind === "audio" ? " · ▶ playable" : ""}</div>
                <div style={{ fontSize: 12.5, lineHeight: 1.4, color: c.kind === "verdict" ? "var(--accent-ink)" : "var(--ink)", fontWeight: c.kind === "verdict" ? 600 : 400 }}>{c.v}</div>
              </div>
            </div>
          ))}
        </div>
        <p className="muted" style={{ marginTop: 12 }}>Real recording, real verdict, every link to source — walk from the BLOCK back to the audio segment. Independently reproducible on the council.</p>
      </div>
    </div>
  );
}
