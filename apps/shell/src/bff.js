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
// validate a candidate token against a gated route — only a SUCCESSFUL (2xx) response confirms it
// (the token actually worked). A 401 is an explicit reject; a 5xx/transport error is inconclusive and
// must NOT store an unvalidated token (the next real call re-raises the gate if so) — so require r.ok.
export const validateToken = async (candidate) => {
  try {
    const r = await fetch(BASE + "/v1/meta", { headers: candidate ? { Authorization: `Bearer ${candidate}` } : {} });
    return r.ok;
  } catch { return false; }
};
// logout = forget the token + raise the auth-required signal so the gate re-shows (no full reload).
export const logout = () => { clearToken(); try { window.dispatchEvent(new Event("lithrim:auth-required")); } catch {} };
// SESSION-MENU-1: a PROACTIVE sign-in trigger — raise the same gate signal AuthGate already listens
// for, so the login screen opens on demand (not only on a 401). On an open server the entered token
// validates against /v1/meta; cancel returns to the app (the LoginScreen is now cancelable).
export const signIn = () => { try { window.dispatchEvent(new Event("lithrim:auth-required")); } catch {} };

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
   in_process=true forces the in-process v2 council — the path an authored judge re-votes on.
   CHAT-FRESH-GRADE-1: `confirm` carries the human's in-DOM cost-confirm so a chat "run eval"
   grades FRESH (the same cost-gated path the TopBar "Run live" button takes); it is sent only
   when set (the $0 replay never carries it) and rides the run-eval body harmlessly. */
export const runEval = ({ agent = "ws0_default", live = false, in_process = false, confirm = false, case_id = null } = {}) =>
  call("/v1/run-eval", {
    method: "POST",
    body: { agent, live, in_process, ...(confirm ? { confirm } : {}), ...(case_id ? { case_id } : {}) },
  });

/* GET /v1/runs — the run-history list (newest-first). Each row's run_id round-trips
   to getRunAudit(run_id). (UAP-3 R6/S-BS-56; all via BASE, no hardcoded :8787.)
   RUN-TRAIL-CASE-SCOPE: optional { agent, caseId } filters (additive; exact case id). */
export const getRuns = (limit = 50, { agent, caseId } = {}) => {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (agent) qs.set("agent", agent);
  if (caseId) qs.set("case_id", caseId);
  return call(`/v1/runs?${qs.toString()}`);
};

/* GET /v1/reports/{case_id} — REPORT-HYDRATE-1: the LATEST persisted report record for a case
   (the run-eval record shape, honestly labeled by its stored grade_path; a pure $0 read).
   404 when the case has no saved run for this agent — the caller keeps its empty state. */
export const getCaseReport = (agent = "ws0_default", caseId) =>
  call(`/v1/reports/${encodeURIComponent(caseId)}?agent=${encodeURIComponent(agent)}`);

/* POST /v1/eval-pack/run — batch a pack of agents (R6). replay ($0) by default. */
export const runEvalPack = ({ pack_id, agents = ["ws0_default"], live = false }) =>
  call("/v1/eval-pack/run", { method: "POST", body: { pack_id, agents, live } });

/* POST /v1/cases/grade — RUN-ALL-1: grade the whole ingested cohort and return {matrix, summary,
   scorecard}. case_ids null → ALL cases. live/in_process are the SAME paid knobs as run-eval; a
   paid cohort grade is the human's cost-confirmed call (never an agent tool). The `scorecard` field
   is the case_id-attributed consolidated report the inline ScorecardCard renders. */
export const gradeCases = ({ agent = "ws0_default", live = false, in_process = false, case_ids = null } = {}) =>
  call("/v1/cases/grade", {
    method: "POST",
    body: { agent, live, in_process, ...(case_ids ? { case_ids } : {}) },
  });

/* POST /v1/cases/ingest/preview — CE-INGEST-FRONTDOOR-1: decode an uploaded JSON/JSONL/CSV blob,
   generate/select a JUTE template, apply it, and return {fmt, columns, count, sample_cases,
   template} for the human to validate. Pins + writes NOTHING. extraction_rules is the field-mapping
   correction channel (re-preview to refine). A bad blob / non-convergence is a 422 with the reason. */
export const ingestPreview = ({ raw, fmt = "auto", filename = "", extraction_rules = "", agent = "ws0_default" }) =>
  call("/v1/cases/ingest/preview", { method: "POST", body: { raw, fmt, filename, extraction_rules, agent } });

/* POST /v1/cases/ingest/commit — pin the human-APPROVED template + upsert the corpus (no LM gen).
   The decode is deterministic, so it reproduces exactly the cases shown in /preview. */
export const ingestCommit = ({ approved_template, raw, fmt = "auto", filename = "", extraction_rules = "", agent = "ws0_default" }) =>
  call("/v1/cases/ingest/commit", { method: "POST", body: { approved_template, raw, fmt, filename, extraction_rules, agent } });

/* TOOL-AUTHOR-1: per-workspace MCP/API tool authoring. createTool persists a kind:tool manifest
   (+ optional flag bind) via POST /v1/tools (audited); listTools returns {authored, declared};
   testTool health-checks a stdio-MCP manifest (list_tools); deleteTool removes an authored tool. */
export const createTool = ({ manifest, bind = null, agent = "ws0_default", rationale = "" }) =>
  call("/v1/tools", { method: "POST", body: { manifest, bind, agent, rationale } });
export const listTools = () => call("/v1/tools");
export const testTool = (manifest) => call("/v1/tools/test", { method: "POST", body: { manifest } });
export const deleteTool = (toolId) => call(`/v1/tools/${encodeURIComponent(toolId)}`, { method: "DELETE" });

export const getCorpus = () => call("/v1/corpus");
/* GET /v1/cases/browser — CASE-BROWSER-1: the browsable union of every case load_case can
   resolve for the agent (pinned source → pack fixtures → ingested), each row carrying the
   by-construction label (labeled/defect), this agent's run count, and the baseline-freshness
   state (fresh | stale | none | unknown) for the $0-replay dot. The Cases tab's discovery read. */
export const listCaseBrowser = (agent = "ws0_default") =>
  call(`/v1/cases/browser?agent=${encodeURIComponent(agent)}`);

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

/* POST /v1/criterion-jute/generate — CRITERION-JUTE-1d: the tool-grounded criterion loop. An SME
   picks a tool+call, a plain-English criterion seeds generation of the per-case arguments_jute (1b),
   the bidirectional subsumption corpus gate runs (1c), and the mcp_call + arguments_jute contract
   PINS on pass (1a). commit:false = a $0 PREVIEW ({status:"preview", arguments_jute,
   arguments_jute_sha256, gate_report}); commit:true + a passing gate PINS through the same audited
   put path ({status:"pinned", contract, gate_report}); a failing gate 422s (naming the case ids). */
export const generateCriterionJute = ({ flag_code, tool, call, criterion = "", sample_case = {}, n_generations = 3, commit = false, agent = "ws0_default" }) =>
  call("/v1/criterion-jute/generate", { method: "POST", body: { flag_code, tool, call, criterion, sample_case, n_generations, commit, agent } });

/* GET /v1/grounding-contract/types — FAUTH-2 (G3): the active pack's REGISTERED grounding
   executor keys (suppress ∪ floor) — the pack-true contract-type list ContractBuilder drives its
   selector from, so a non-coder can only pick a type the author-time gate will accept (and that
   ground() won't raise on at grade time). READ-ONLY, $0. The builder falls back to its static
   CONTRACT_TYPES if this rejects (offline / first paint). */
export const getGroundingContractTypes = () => call("/v1/grounding-contract/types");

/* GET /v1/agents/{agent}/readiness — the agent↔pack READINESS preflight ($0, offline): does this
   agent's resolved ontology carry every fact-check the pinned pack declares (with a registered
   executor + a permitted tool)? Returns {ok, pack, agent, findings:[{check,severity,code,message,
   remediation}], assessed}. Surfaces the silent hole where a pack-declared floor never fires because
   the graded (agent) ontology lacks its contract. The shell renders it inline as a setup-gaps card. */
export const getReadiness = (agent = "ws0_default") =>
  call(`/v1/agents/${encodeURIComponent(agent)}/readiness`);

/* POST /v1/criterion — NARR-5-CRIT-b: the CriterionBuilder card's direct, audited mint of a new
   GRADEABLE criterion (a scoreable taxonomy code) into the active tier:core pack's taxonomy snapshot
   (tiers + lenses + tier1_owners) + the ontology overlay. The sanctioned snapshot writer — the
   human's Save is the SOLE write of the contract-of-record (the agent never mints a code). A 409
   (duplicate) / 422 (non-core pack / bad owner / bad tier / malformed code) throws so the card can
   surface it. $0, never a paid run. */
export const postCriterion = (criterion, agent = "ws0_default") =>
  call("/v1/criterion", { method: "POST", body: { ...criterion, agent } });

/* POST /v1/meta-verdict — META-VERDICT-1: a clinician's INDEPENDENT verdict + judge meta-audit
   on a run (Clinical Scribe Review Layer-3). Writes ONE immutable AuditRecord (action=meta_verdict). $0 —
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

/* ── CE-PROVIDER-UI (Build B): the in-app "Connect AI" surface (SPEC_COMMUNITY_EDITION §3.2) ──
   POST /v1/provider/config — configure the user's LLM provider key IN-APP, capability-oriented:
   `plane` is "grading" (the council judge LM, required) | "assistant" (chat-authoring, optional).
   The endpoint TEST-probes the key read-only, then writes it ONLY to the gitignored .provider_env
   (never SQLite/the response). `endpoint` (Azure api_base), `model`, `role` (one grading judge)
   are optional. Returns {ok, plane, provider, last_tested} — NEVER the key. Via call() so it carries
   the auth header. A failing probe / bad config (4xx) throws so the panel can surface it. */
export const configProvider = ({ plane = "grading", provider, api_key, endpoint, model, role } = {}) =>
  call("/v1/provider/config", {
    method: "POST",
    body: {
      plane, provider, api_key,
      ...(endpoint ? { endpoint } : {}),
      ...(model ? { model } : {}),
      ...(role ? { role } : {}),
    },
  });

/* GET /v1/provider/status — which planes are configured + provider/model/last_tested (never the
   key), so the panel shows connected / needs-setup per capability. $0 read, via call(). */
export const getProviderStatus = () => call("/v1/provider/status");

/* ── CONNECT-AI-CONSOLIDATE-1: the 2-section "Connect AI" — assign a {provider, model} to ONE
   consumer (a judge or the compulsory chat_assistant) REUSING the provider's already-stored key.
   The bind body carries NO key (keys entered once in the Providers section); the response carries
   NO key. role ∈ {risk_judge, policy_judge, faithfulness_judge, chat_assistant}. */

/* POST /v1/roles/bind {role, provider, model} — bind a consumer to an already-connected provider's
   model, reusing the stored key. A judge writes LITHRIM_LLM_*_<ROLE>; chat_assistant writes the
   LITHRIM_CHAT_* contract. 422 if the provider isn't connected / unknown role / a bad endpoint /
   a failing probe. Returns {ok, role, provider, model} — NEVER a key. */
export const bindRole = ({ role, provider, model, endpoint, api_version } = {}) =>
  call("/v1/roles/bind", {
    method: "POST",
    // NEW-G1: a per-role endpoint/api_version rides the body ONLY when provided (azure /
    // openai_compatible) — omitted otherwise so the bind falls back to the stored global.
    body: {
      role, provider, model,
      ...(endpoint ? { endpoint } : {}),
      ...(api_version ? { api_version } : {}),
    },
  });

/* GET /v1/roles/bindings — the non-secret per-consumer readout ({roles: {role → {provider, model} |
   null}}) + connected_providers (those with a stored key, for the Providers list). NEVER a key. */
export const getRoleBindings = () => call("/v1/roles/bindings");

/* REVIEWER-MODE (single vs multiple reviewers): the per-agent reviewer roster. GET returns
   {reviewer_roster: [role,…]|null (null = panel), panel: [all pack reviewers]}. POST sets it —
   a single-role roster runs that one reviewer; null/[] = the panel (full pack roster). Audited. */
export const getCouncilRoster = (agent) => call(`/v1/council/roster${agent ? `?agent=${encodeURIComponent(agent)}` : ""}`);
export const setCouncilRoster = ({ agent, roster } = {}) =>
  call("/v1/council/roster", { method: "POST", body: { agent, roster } });

/* ── MODEL-REGISTRY-1c: the configured-model pool (pick-from-pool role bind) ──────
   The reusable model pool that backs Connect AI's "Model pool" section: register a
   capability-annotated model once, then BIND each fixed judge role to a pool entry
   instead of re-typing provider/model/key per role. All via call() (auth header).
   `logprobs` is the load-bearing capability — a logprobs:false model drives the ⚠
   "no logprobs — confidence dark" hint at pick time. NEVER a key on any response. */

/* GET /v1/models/catalog?live=… — the capability-aware catalog: curated presets per
   provider ({model, logprobs, context_window, cost_tier}) + the Azure {models, note}.
   `live=true` opts into a fresh provider-listed fetch (MODEL-REGISTRY-1b) when supported;
   the panel renders gracefully whether or not a source/live field comes back. $0 read. */
export const getModelCatalog = ({ live = false } = {}) =>
  call(`/v1/models/catalog${live ? "?live=true" : ""}`);

/* POST /v1/models — register a model into the pool. The key is read-only test-probed,
   then written write-only to .provider_env (never SQLite/the response). Returns the
   non-secret public entry ({id, provider, model, endpoint, capabilities, bound_roles}) —
   NEVER the key. `endpoint` is required for provider="azure". 400 on a failing probe. */
export const registerModel = ({ id, provider, model, endpoint, api_key } = {}) =>
  call("/v1/models", {
    method: "POST",
    body: { id, provider, model, ...(endpoint ? { endpoint } : {}), api_key },
  });

/* GET /v1/models — the configured-model pool (non-secret metadata + capabilities only). */
export const listModels = () => call("/v1/models");

/* DELETE /v1/models/{id} — drop a pool entry AND its write-only key. */
export const deleteModel = (id) =>
  call(`/v1/models/${encodeURIComponent(id)}`, { method: "DELETE" });

/* POST /v1/models/{id}/bind {role} — bind a pool entry to one of the 3 fixed roles
   (risk_judge|policy_judge|faithfulness_judge); the role references the entry instead of
   re-typing it. Phase-1 binds the same-provider trio (cross-provider-per-role is a backend
   seam). 404 unknown id · 409 entry with no persisted key · 400 bad config. */
export const bindModel = (id, role) =>
  call(`/v1/models/${encodeURIComponent(id)}/bind`, { method: "POST", body: { role } });

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

/* GET /v1/runs/{id}/history — RUNTRAIL-6: the lineage of prior versions for a run
   ({run_id, history: [...]}); each version carries verdict + grade_path. */
export const getRunHistory = (runId) =>
  call(`/v1/runs/${encodeURIComponent(runId)}/history`);

/* GET /v1/runs/{id}/rehydrate — RUNTRAIL-6: reconstruct a run's verdict from the
   stored blob ($0; {verdict, ...}; 404 on an unknown run). */
export const rehydrateRun = (runId) =>
  call(`/v1/runs/${encodeURIComponent(runId)}/rehydrate`);

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

/* POST /v1/judges — PHASE2-C: mint a NEW first-class judge over the active pack's taxonomy
   snapshot. The authoring bundle is {role, lens_codes (codes it may raise), owned_codes (⊆ lens —
   the one-strike owner set; empty = corroborate-only), model_id?, role_prompt?, rationale}. The
   snapshot stays the by-construction contract — the server splices production_judges + lenses +
   tier1_owners (audited) and binds the deployment; the frozen consensus seam is untouched. Returns
   the non-secret entry {role, lens_codes, owned_codes, model, bound_roles, audit_id} — NEVER a key.
   422 on admissibility failure (owned⊄lens / code∉taxonomy / empty lens / role collision / non-core
   pack) with a `detail` string; the card surfaces it inline. $0 — authoring, never a paid run. */
export const createJudge = ({ role, lens_codes, owned_codes, model_id, role_prompt, rationale = "" } = {}) => {
  // rationale rides the query param (the §2B audit "why"), mirroring putJudge/deleteJudge — the
  // endpoint reads it via Query(); the authoring bundle stays in the body. (Sending it in the body
  // silently dropped the audit why — P2-B critic Q6.)
  const q = new URLSearchParams({ rationale });
  return call(`/v1/judges?${q.toString()}`, {
    method: "POST",
    body: {
      role,
      lens_codes,
      owned_codes,
      ...(model_id ? { model_id } : {}),
      ...(role_prompt ? { role_prompt } : {}),
    },
  });
};

/* ── UAP-4: the calibration trainer — optimize a judge, see the honest held-out Δ ── */

/* POST /v1/judges/{role}/optimize — PAID. Optimize the judge against the bench-accept
   metric on the by-construction calibration split + measure the held-out Δ
   (precision/recall before→after, WIN-OR-LOSS). The route refuses (422) without
   confirm=true, so the shell gates it behind an in-DOM cost modal (S-BS-69; never
   window.confirm). A measured Δ — including ≤0 — is the loop-closure; the gate is
   never loosened. Returns {role, n_train, n_heldout, baseline, optimized, delta, …}. */
/* optimize-on-subset: pass caseIds to scope the calibration to a CHOSEN case set (the Cases
   ids), not the whole workspace. Omitted/empty → whole-workspace (back-compat). A selector,
   never a paid knob — confirm=true is still required (mirrors the limit pattern). */
export const optimizeJudge = (role, { confirm = false, limit, caseIds } = {}) =>
  call(`/v1/judges/${encodeURIComponent(role)}/optimize`, {
    method: "POST",
    body: {
      confirm,
      ...(limit != null ? { limit } : {}),
      ...(caseIds && caseIds.length ? { case_ids: caseIds } : {}),
    },
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

/* GET /v1/reliability/{agent} — RIGOR-1: the statistical-rigour reliability metrics
   (Fleiss/Cohen kappa · 10-bin ECE + Brier · pairwise-error phi + effective votes ·
   floor selective-prediction · intra-judge stability), COMPUTED from this agent's OWN
   persisted runs + gold. $0 pure read. Each metric carries an honest `insufficient` flag
   (null value + reason) when it can't be computed — never a fabricated number. 404 on an
   unknown agent. Shape: {agent, n_runs, metrics: {inter_judge_kappa, cohen_kappa_vs_gold,
   ece, brier, error_phi, effective_votes, intra_judge_stability, selective_prediction}}. */
export const getReliability = (agent = "ws0_default") =>
  call(`/v1/reliability/${encodeURIComponent(agent)}`);

/* GET /v1/reliability/{agent}/sweep — RIGOR-1 / Q1 (NEW-G3): the single-reviewer K-sweep
   self-consistency curve (flip-rate / majority-convergence / variance with Wilson CIs, for
   K = 1..k_max), COMPUTED from this agent's OWN per-sample scores. $0 pure read; NO gold (the
   sweep measures a reviewer against itself). `insufficient` + reason when no sampled runs — never
   a fabricated curve. 404 on an unknown agent. Shape: {agent, n_cases, sweep: {insufficient,
   k_max, series: [{k, flip_rate, majority_convergence, variance}]}}. */
export const getReliabilitySweep = (agent = "ws0_default", { k_max, role } = {}) => {
  const qs = new URLSearchParams();
  if (k_max != null) qs.set("k_max", String(k_max));
  if (role != null) qs.set("role", role);
  const q = qs.toString();
  return call(`/v1/reliability/${encodeURIComponent(agent)}/sweep${q ? `?${q}` : ""}`);
};
