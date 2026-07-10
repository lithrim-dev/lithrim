/* jp1.jsx — Phase 1: First contact (ESM port; AgentMsg imported from chrome.jsx). */
import { Icon } from "../icons.jsx";
import { AgentMsg } from "./chrome.jsx";
import { AGENT_TYPES, PACK, PILLARS } from "./journeyData.js";

export function Center1({ agent, setAgent }) {
  return (
    <div className="convo-inner">
      <AgentMsg beat="Act 1 · First contact"
        lead="Welcome to Lithrim. Bench and the Healthcare pack are installed — let's get your first agent under evaluation.">
        <p className="muted">What kind of agent are you working with? I'll tailor the judges and taxonomy to match.</p>
        <div className="icard" style={{ marginTop: 14 }}>
          <div className="icard-bd">
            <div className="pick-grid">
              {AGENT_TYPES.map((a) => (
                <button key={a.id} className={"pick-card" + (agent === a.id ? " sel" : "")} onClick={() => setAgent(a.id)}>
                  <span className="pic"><Icon name={a.icon} size={18} /></span>
                  <span>
                    <span className="pn">{a.name}</span>
                    <span className="pd">{a.desc}</span>
                  </span>
                  <span className="pcheck"><Icon name="check" size={16} sw={2.4} /></span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </AgentMsg>

      <div className="msg user">
        <div className="av user">JR</div>
        <div className="content">
          <div className="name">Jordan</div>
          <p>Clinical Scribe — it drafts our visit notes from the encounter audio.</p>
        </div>
      </div>

      <AgentMsg lead="A clinical scribe — good. I'll need two things to start judging it.">
        <p className="muted">Your agent's system prompt, so the judges know its job — and a model key to run the council. Bring your own; it never leaves your machine.</p>
        <div className="icard" style={{ marginTop: 14 }}>
          <div className="icard-hd">
            <span className="ic"><Icon name="note" size={15} /></span>
            <span className="ttl">Agent meta</span>
            <span className="sub">scribe-v4</span>
          </div>
          <div className="icard-bd">
            <div className="field" style={{ marginBottom: 13 }}>
              <span className="flbl">System prompt</span>
              <div className="prompt-box">
                You are a clinical scribe. Given a visit recording, produce a structured SOAP note.
                Record every medication with its exact name and dosage. Never infer findings that were
                not stated. Preserve the clinician's plan verbatim where possible…
                <div className="ph-fade" />
              </div>
            </div>
            <div className="field-grid">
              <div className="field">
                <span className="flbl">Model key — BYOK</span>
                <div className="kv-input">
                  <Icon name="key" size={14} style={{ color: "var(--muted)", flex: "0 0 auto" }} />
                  <span className="vk">sk-ant-•••• •••• •••• 9f2a</span>
                  <span className="ok"><Icon name="check" size={13} sw={2.4} /> validated</span>
                </div>
              </div>
              <div className="field">
                <span className="flbl">Provider</span>
                <div className="select"><span>Anthropic · claude-3.7</span><span className="chev"><Icon name="chevD" size={14} /></span></div>
              </div>
            </div>
          </div>
          <div className="icard-foot">
            <span className="note">key stored locally · never transmitted</span>
            <span className="linkb" style={{ marginLeft: "auto" }}>Continue to the reveal <Icon name="arrowR" size={13} /></span>
          </div>
        </div>
      </AgentMsg>
    </div>
  );
}

export function Artifact1() {
  return (
    <div>
      <div className="pack-hero">
        <div className="ph-ic"><Icon name="book" size={22} /></div>
        <div style={{ minWidth: 0 }}>
          <div className="ph-name">{PACK.name}</div>
          <div className="ph-ver">{PACK.ver} · just installed</div>
        </div>
        <div className="ph-status"><span className="tag pass"><Icon name="check" size={11} /> ready</span></div>
      </div>

      <div className="art-sec">
        <div className="art-h2">What's inside</div>
        <div className="tiles">
          <div className="tile"><div className="tk">Scenarios</div><div className="tv">{PACK.scenarios}</div><div className="td">real encounters · labels by construction</div></div>
          <div className="tile"><div className="tk">Pillars</div><div className="tv">4</div><div className="td">judged per note</div></div>
          <div className="tile"><div className="tk">Taxonomy</div><div className="tv">{PACK.taxonomy}</div><div className="td">failure codes</div></div>
          <div className="tile"><div className="tk">Judges</div><div className="tv">{PACK.judges}</div><div className="td">cross-provider v2 trio</div></div>
        </div>
      </div>

      <div className="art-sec" style={{ marginBottom: 4 }}>
        <div className="art-h2">The four pillars</div>
        <div style={{ border: "1px solid var(--border)", borderRadius: "var(--r)", padding: "2px 13px" }}>
          {PILLARS.map((p) => (
            <div className="pillar-row" key={p.key}>
              <span className="pr-ic" style={{ background: p.color + "22", color: p.color }}><Icon name={p.icon} size={15} /></span>
              <div>
                <div className="pr-name">{p.name}</div>
                <div className="pr-desc">{p.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
