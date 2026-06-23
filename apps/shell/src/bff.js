/* bff.js — the React↔Python bridge client (WS-5-BFF).
   A thin fetch wrapper over the local FastAPI BFF (apps/bff/, the judge-capability
   API v1). Base URL = VITE_BFF_URL when set (e.g. an absolute Tauri/VPC target),
   else "" so requests go through the vite dev proxy (/v1 → :8787). See SPEC §5. */

const BASE = import.meta.env.VITE_BFF_URL ?? "";
// UI-LOGIN-1: the BFF auth token is a RUNTIME client credential — entered/cleared from the UI
// and stored in localStorage, never baked into the bundle (so it's rotatable without a rebuild
// and stays out of the JS). A build-baked VITE_BFF_TOKEN still works as a fallback. When the
// server gate is off (no LITHRIM_BFF_TOKEN) no 401 ever fires, so the login gate never shows.
const TOKEN_KEY = "lithrim_bff_token";
export const getToken = () => {
  try { const t = localStorage.getItem(TOKEN_KEY); if (t) return t; } catch {}
  return import.meta.env.VITE_BFF_TOKEN || "";
};
export const hasStoredToken = () => { try { return !!localStorage.getItem(TOKEN_KEY); } catch { return false; } };
export const setToken = (t) => { try { localStorage.setItem(TOKEN_KEY, t); } catch {} };
export const clearToken = () => { try { localStorage.removeItem(TOKEN_KEY); } catch {} };
const authHeader = () => { const t = getToken(); return t ? { Authorization: `Bearer ${t}` } : {}; };
// validate a candidate token against a gated route — non-401 (incl. 200/500) = the gate accepted it.
export const validateToken = async (candidate) => {
  try {
    const r = await fetch(BASE + "/v1/meta", { headers: candidate ? { Authorization: `Bearer ${candidate}` } : {} });
    return r.status !== 401;
  } catch { return false; }
};
// logout = forget the token + raise the auth-required signal so the gate re-shows (no full reload).
export const logout = () => { clearToken(); try { window.dispatchEvent(new Event("lithrim:auth-required")); } catch {} };

async function call(path, { method = "GET", body, headers } = {}) {
  const merged = { ...(body ? { "Content-Type": "application/json" } : {}), ...authHeader(), ...(headers || {}) };
  const res = await fetch(BASE + path, {
    method,
    headers: Object.keys(merged).length ? merged : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    if (res.status === 401) { try { window.dispatchEvent(new Event("lithrim:auth-required")); } catch {} }
    const detail = await res.text().catch(() => "");
    throw new Error(`${method} ${path} → ${res.status}${detail ? `: ${detail}` : ""}`);
  }
  return res.json();
}

/* POST /v1/run-eval — drive one case end-to-end. replay (live=false) is the $0
   default; live=true opts into one real, paid council run on the configured backend
   (LITHRIM_COUNCIL_BACKEND: in_process [the OSS default, BYO key] | http [:8002]);
   in_process=true forces the in-process v2 council — the path an authored judge re-votes on. */
export const runEval = ({ agent = "ws0_default", live = false, in_process = false, case_id = null } = {}) =>
  call("/v1/run-eval", { method: "POST", body: { agent, live, in_process, ...(case_id ? { case_id } : {}) } });

/* GET /v1/runs — the run-history list (newest-first). Each row's run_id round-trips
   to getRunAudit(run_id). (UAP-3 R6/S-BS-56; all via BASE, no hardcoded :8787.) */
export const getRuns = (limit = 50) => call(`/v1/runs?limit=${encodeURIComponent(limit)}`);

/* POST /v1/eval-pack/run — batch a pack of agents (R6). replay ($0) by default. */
export const runEvalPack = ({ pack_id, agents = ["ws0_default"], live = false }) =>
  call("/v1/eval-pack/run", { method: "POST", body: { pack_id, agents, live } });

export const getCorpus = () => call("/v1/corpus");
/* GET /v1/cases — NARR-LOOP: the active workspace's INGESTED eval cases (case_id + fidelity
   flags). Self-fetched by the Corpus tab so ingested cases survive a reload. */
export const listCases = () => call("/v1/cases");
export const getOntology = (agent = "ws0_default") =>
  call(`/v1/ontology?agent=${encodeURIComponent(agent)}`);

/* GET /v1/case — the SOURCE INPUT the council grades (CHATBIND-3): transcript + artifact
   (generic shape — JSON or free text, varies by domain) + the by-construction planted label
   (expected_safety_flags + injection_recipe) + record conditions. $0 read. */
export const getCase = (agent = "ws0_default", caseId = null) =>
  call(`/v1/case?agent=${encodeURIComponent(agent)}` + (caseId ? `&case_id=${encodeURIComponent(caseId)}` : ""));

/* PUT /v1/ontology — persist an edited ontology to a non-committed working copy
   (WS-5d). The body is the full ontology JSON; the BFF validates it (round-trip +
   snapshot lint) and rejects a malformed/snapshot-violating write with 422. */
export const putOntology = (ontology, agent = "ws0_default") =>
  call(`/v1/ontology?agent=${encodeURIComponent(agent)}`, { method: "PUT", body: ontology });

/* POST /v1/grounding-contract — EVAL-FLOW (W1b): the ContractBuilder card's direct, audited
   write of ONE verification_contract (replace-by-flag-code, idempotent) into the active agent's
   ontology — the SAME store the grade consumes and the rail's Ground-truth step reads. Reuses
   the SAME bound op the add_grounding_contract chat tool uses (no new write logic; $0). A 404
   (unknown flag) / 422 (malformed) throws so the card can surface it. */
export const putGroundingContract = (contract, agent = "ws0_default") =>
  call("/v1/grounding-contract", { method: "POST", body: { ...contract, agent } });

/* GET /v1/grounding-contract/types — FAUTH-2 (G3): the active pack's REGISTERED grounding
   executor keys (suppress ∪ floor) — the pack-true contract-type list ContractBuilder drives its
   selector from, so a non-coder can only pick a type the author-time gate will accept (and that
   ground() won't raise on at grade time). READ-ONLY, $0. The builder falls back to its static
   CONTRACT_TYPES if this rejects (offline / first paint). */
export const getGroundingContractTypes = () => call("/v1/grounding-contract/types");

/* POST /v1/criterion — NARR-5-CRIT-b: the CriterionBuilder card's direct, audited mint of a new
   GRADEABLE criterion (a scoreable taxonomy code) into the active tier:core pack's taxonomy snapshot
   (tiers + lenses + tier1_owners) + the ontology overlay. The sanctioned snapshot writer — the
   human's Save is the SOLE write of the contract-of-record (the agent never mints a code). A 409
   (duplicate) / 422 (non-core pack / bad owner / bad tier / malformed code) throws so the card can
   surface it. $0, never a paid run. */
export const postCriterion = (criterion, agent = "ws0_default") =>
  call("/v1/criterion", { method: "POST", body: { ...criterion, agent } });

/* POST /v1/meta-verdict — META-VERDICT-1: a clinician's INDEPENDENT verdict + judge meta-audit
   on a run (ClinVerdict Layer-3). Writes ONE immutable AuditRecord (action=meta_verdict). $0 —
   it adds an attestation, it never changes the verdict or fires a paid run. judge_fallacy_code
   (only on dissent) is a closed enum; an out-of-enum code 422s so the form can surface it. */
export const recordMetaVerdict = (mv) =>
  call("/v1/meta-verdict", { method: "POST", body: mv });

/* ── UAP-1: the config-plane write-path + the audit streams (all via BASE; S-BS-50,
   no hardcoded :8787) ─────────────────────────────────────────────────────────── */

/* GET/PUT /v1/agent — load + persist an assembled Agent (judges + ontology + tools +
   kb) to the config plane (R1). actor is the §2B "who": passed as the X-Actor header
   so a real SME attributes the write (else the BFF dev-default). */
export const getAgent = (name = "ws0_default") =>
  call(`/v1/agent?name=${encodeURIComponent(name)}`);

export const putAgent = (agent, { actor, rationale = "" } = {}) =>
  call(`/v1/agent?rationale=${encodeURIComponent(rationale)}`, {
    method: "PUT",
    body: agent,
    headers: actor ? { "X-Actor": actor } : undefined,
  });

/* GET/PUT /v1/conversation — PERSIST-CONV: the durable chat thread (the {role, text?, parts?}
   message list) per agent, so a browser refresh no longer wipes the conversation. A PLAIN
   (un-audited) per-turn upsert — no actor/X-Actor, $0; the config writes inside the chat are
   audited on their own routes. GET on an agent with no stored thread returns {thread: []}. */
export const getConversation = (agent = "ws0_default") =>
  call(`/v1/conversation?agent=${encodeURIComponent(agent)}`);

export const putConversation = (agent, thread) =>
  call("/v1/conversation", { method: "PUT", body: { agent, thread } });

/* DELETE /v1/conversation — the "clear conversation" affordance: drop this agent's stored
   thread. A PLAIN, idempotent clear (un-audited per-turn UX state); clearing an absent thread
   is a benign no-op ({removed: false}), never a 404. */
export const deleteConversation = (agent = "ws0_default") =>
  call(`/v1/conversation?agent=${encodeURIComponent(agent)}`, { method: "DELETE" });

/* ── CRUD-1: the config-plane agent switcher + the blank-slate create/delete ───── */

/* GET /v1/agents — the config-plane agent names (the rail switcher). */
export const listAgents = () => call("/v1/agents");

/* ── workspaces: the switchable domain-setup boundary (the multitenancy primitive) ──
   A workspace owns its config DB / runs / audit / ontology + a pinned domain pack.
   Switching repoints all of it server-side; the shell reloads agents to reflect it. */
export const listWorkspaces = () => call("/v1/workspaces");
/* GET /v1/packs — the discoverable domain packs a workspace can pin (P3: 'install a pack'
   = make it discoverable, then it shows up here for selection). */
export const listPacks = () => call("/v1/packs");
/* GET /v1/meta — the live status-bar state (workspace/pack/agents/judges/runs/version). */
export const getMeta = () => call("/v1/meta");
export const switchWorkspace = (name) =>
  call("/v1/workspace", { method: "POST", body: { name } });
export const createWorkspace = ({ name, pack = "_core", actor = "you@local" }) =>
  call("/v1/workspaces", { method: "POST", body: { name, pack, actor } });

/* ── NARR-6: the StoryWorld connector — connect the admin API → batch-ingest real cases ──
   POST /v1/connector/config — run a read-only Test with the supplied key; on a clean 200 the
   BFF writes the key ONLY to the gitignored .connector_env (never SQLite/the response) +
   persists base_url+last_tested. Returns {connector_id, base_url, last_tested, status} — never
   the key. The shell masks the key input and surfaces the 200/401/timeout status. */
export const testConnector = ({ base_url, x_api_key, connector_id = "storyworld_admin" } = {}) =>
  call("/v1/connector/config", { method: "POST", body: { connector_id, base_url, x_api_key } });

/* CONN-1: GET /v1/connectors — the ingest-capable connectors declared in the active pack's tool
   registry (plugins.tool_plugins()). Display-safe fields only ({connector_id, label,
   default_base_url, transport}); never a key. The picker renders this list — no hardcoded source. */
export const listConnectors = () => call("/v1/connectors");

/* CONN-1: POST /v1/connector/ingest — generic batch ingest, dispatched by connector_id to a
   per-connector pull adapter (the key loads server-side from .connector_env, never sent). Returns
   {count, sessions, cases, errors_trapped}. $0 (no paid council; the floor-grade is NARR-7). */
export const ingestConnector = ({ connector_id, limit = 50, offset = 0, agent } = {}) =>
  call("/v1/connector/ingest", {
    method: "POST",
    body: { connector_id, limit, offset, ...(agent ? { agent } : {}) },
  });

/* GET /v1/agent/template — the committed blank-slate template (ws0_default.json), the
   clone source for a fresh agent. Independent of the active workspace, since a freshly
   created workspace starts with NO agents. */
export const getAgentTemplate = () => call("/v1/agent/template");

/* PUT a blank-slate but RUNNABLE agent: authoring-blank (no judges/tools/kb) yet it
   clones the committed template's ontology + Dataset so create → author a judge →
   RUN → see it grade works immediately from clean (the Dataset is BOUND, not empty, so
   run_eval can load a case). The judge-config store is global, so a fresh agent shares
   whatever lenses exist; "blank" here is the agent's roster + a clean chat. */
export async function createAgent(name, { actor } = {}) {
  const seed = await getAgentTemplate();
  const ep = seed.eval_profile || {};
  const agent = {
    name,
    eval_profile: {
      judges: [],
      council_config: ep.council_config || {},
      ontology_ref: ep.ontology_ref || "",
      ontology_path: ep.ontology_path || "",
      tools: [],
      kb_bindings: {},
      severity_map_ref: ep.severity_map_ref || "",
    },
    dataset: seed.dataset,
  };
  return putAgent(agent, { actor, rationale: `blank-slate agent ${name} (CRUD-1 New evaluation)` });
}

/* DELETE /v1/agent?name= — remove an agent eval-profile (audited). The BFF refuses
   (422) the seed default + the last remaining agent; 404 on unknown. Throws on a
   guard/404 so the caller can surface it. */
export const deleteAgent = (name, { actor, rationale = "" } = {}) => {
  const q = new URLSearchParams({ name });
  if (rationale) q.set("rationale", rationale);
  return call(`/v1/agent?${q.toString()}`, {
    method: "DELETE",
    headers: actor ? { "X-Actor": actor } : undefined,
  });
};

/* DELETE /v1/judges/{role} — revert a judge to its default lens (audited). 404 on an
   unknown role; a known-but-already-default role is an idempotent 200 (removed=false). */
export const deleteJudge = (role, { actor, rationale = "" } = {}) => {
  const q = rationale ? `?rationale=${encodeURIComponent(rationale)}` : "";
  return call(`/v1/judges/${encodeURIComponent(role)}${q}`, {
    method: "DELETE",
    headers: actor ? { "X-Actor": actor } : undefined,
  });
};

/* GET /v1/audit — the config-change audit stream (§2B stream 1): who/when/what/why. */
export const getAudit = ({ actor, target_type, target_id, since } = {}) => {
  const q = new URLSearchParams();
  if (actor) q.set("actor", actor);
  if (target_type) q.set("target_type", target_type);
  if (target_id) q.set("target_id", target_id);
  if (since) q.set("since", since);
  const qs = q.toString();
  return call(`/v1/audit${qs ? `?${qs}` : ""}`);
};

/* GET /v1/runs/{id}/audit — the run-provenance report (§2B stream 2). */
export const getRunAudit = (runId) =>
  call(`/v1/runs/${encodeURIComponent(runId)}/audit`);

/* ── UAP-2: judge authoring via ontology-assignment (R2; all via BASE, S-BS-50) ── */

/* GET /v1/judges — the v2 trio: each role + model + assigned lens + questions + refs. */
export const getJudges = (agent = "ws0_default") =>
  call(`/v1/judges?agent=${encodeURIComponent(agent)}`);

/* GET /v1/judges/{role} — one judge's config + the rendered role_key_questions
   ($0 prompt preview). Pass assignedFlags (array) for a live before/after preview of
   a hypothetical assignment — the exact prompt the bridge would send, no model call. */
export const getJudge = (role, { agent = "ws0_default", assignedFlags } = {}) => {
  const q = new URLSearchParams({ agent });
  if (assignedFlags !== undefined) q.set("assigned_flags", (assignedFlags || []).join(","));
  return call(`/v1/judges/${encodeURIComponent(role)}?${q.toString()}`);
};

/* PUT /v1/judges/{role} — assign a flag lens + bind a model + attach validator refs.
   422 on owner↔emit / snapshot / unknown-validator violation. actor rides X-Actor.
   S-BS-153: pass `agent` to ALSO roster this judge onto that agent's eval_profile.judges
   (idempotent, audited, server-side) so authoring it advances the rail's Judges step. */
export const putJudge = (role, judge, { actor, rationale = "", agent } = {}) => {
  const q = new URLSearchParams({ rationale });
  if (agent) q.set("agent", agent);
  return call(`/v1/judges/${encodeURIComponent(role)}?${q.toString()}`, {
    method: "PUT",
    body: judge,
    headers: actor ? { "X-Actor": actor } : undefined,
  });
};

/* ── UAP-4: the calibration trainer — optimize a judge, see the honest held-out Δ ── */

/* POST /v1/judges/{role}/optimize — PAID. Optimize the judge against the bench-accept
   metric on the by-construction calibration split + measure the held-out Δ
   (precision/recall before→after, WIN-OR-LOSS). The route refuses (422) without
   confirm=true, so the shell gates it behind an in-DOM cost modal (S-BS-69; never
   window.confirm). A measured Δ — including ≤0 — is the loop-closure; the gate is
   never loosened. Returns {role, n_train, n_heldout, baseline, optimized, delta, …}. */
export const optimizeJudge = (role, { confirm = false, limit } = {}) =>
  call(`/v1/judges/${encodeURIComponent(role)}/optimize`, {
    method: "POST",
    body: { confirm, ...(limit != null ? { limit } : {}) },
  });

/* ── UAP-5b / R11: the conversational shell's agent loop (SSE) ──────────────────
   POST /v1/chat streams the multi-turn loop. EventSource is GET-only (this needs a
   POST body), so we read the fetch ReadableStream and parse `data: <json>\n\n`
   frames. onEvent is called per event: {event, ...} where event is one of
   assistant_delta | tool_call | tool_result | error | done. Returns a Promise that
   resolves when the stream ends; pass an AbortSignal to cancel. BYO-Claude — the
   loop's tools are author/read/REPLAY only (no paid run is reachable from chat). */
export async function chatStream(
  { message, agent = "ws0_default", actor, history = [], active_case = null } = {},
  { onEvent, signal } = {},
) {
  // ONB-0 (S-BS-87): `history` is the prior conversation turns ([{role, content}]),
  // replayed by the loop as context only — text-only, no paid knob (A-SAFE).
  // NARR-CHAT-LOOP: `active_case` is the case the human is exploring in the UI — the loop
  // names it + defaults show_case/run_eval to it so the chat operates on the case on screen,
  // not the agent's seed. A selector, never a paid knob.
  const res = await fetch(BASE + "/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader(), ...(actor ? { "X-Actor": actor } : {}) },
    body: JSON.stringify({ message, agent, history, ...(active_case ? { active_case } : {}) }),
    signal,
  });
  if (!res.ok || !res.body) {
    const detail = await res.text().catch(() => "");
    throw new Error(`POST /v1/chat → ${res.status}${detail ? `: ${detail}` : ""}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    // SSE frames are delimited by a blank line.
    let sep;
    while ((sep = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      try {
        onEvent?.(JSON.parse(line.slice(5).trim()));
      } catch {
        /* ignore a partial/garbled frame */
      }
    }
  }
}
