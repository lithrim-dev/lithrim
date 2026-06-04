/* bff.js — the React↔Python bridge client (WS-5-BFF).
   A thin fetch wrapper over the local FastAPI BFF (apps/bff/, the judge-capability
   API v1). Base URL = VITE_BFF_URL when set (e.g. an absolute Tauri/VPC target),
   else "" so requests go through the vite dev proxy (/v1 → :8787). See SPEC §5. */

const BASE = import.meta.env.VITE_BFF_URL ?? "";

async function call(path, { method = "GET", body, headers } = {}) {
  const merged = { ...(body ? { "Content-Type": "application/json" } : {}), ...(headers || {}) };
  const res = await fetch(BASE + path, {
    method,
    headers: Object.keys(merged).length ? merged : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${method} ${path} → ${res.status}${detail ? `: ${detail}` : ""}`);
  }
  return res.json();
}

/* POST /v1/run-eval — drive one case end-to-end. replay (live=false) is the $0
   default; live=true opts into one real, paid :8002 call; in_process=true opts into
   the in-process v2 Azure council (paid) — the path an authored judge re-votes on. */
export const runEval = ({ agent = "ws0_default", live = false, in_process = false } = {}) =>
  call("/v1/run-eval", { method: "POST", body: { agent, live, in_process } });

/* GET /v1/runs — the run-history list (newest-first). Each row's run_id round-trips
   to getRunAudit(run_id). (UAP-3 R6/S-BS-56; all via BASE, no hardcoded :8787.) */
export const getRuns = (limit = 50) => call(`/v1/runs?limit=${encodeURIComponent(limit)}`);

/* POST /v1/eval-pack/run — batch a pack of agents (R6). replay ($0) by default. */
export const runEvalPack = ({ pack_id, agents = ["ws0_default"], live = false }) =>
  call("/v1/eval-pack/run", { method: "POST", body: { pack_id, agents, live } });

export const getCorpus = () => call("/v1/corpus");
export const getOntology = (agent = "ws0_default") =>
  call(`/v1/ontology?agent=${encodeURIComponent(agent)}`);

/* PUT /v1/ontology — persist an edited ontology to a non-committed working copy
   (WS-5d). The body is the full ontology JSON; the BFF validates it (round-trip +
   snapshot lint) and rejects a malformed/snapshot-violating write with 422. */
export const putOntology = (ontology, agent = "ws0_default") =>
  call(`/v1/ontology?agent=${encodeURIComponent(agent)}`, { method: "PUT", body: ontology });

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
   422 on owner↔emit / snapshot / unknown-validator violation. actor rides X-Actor. */
export const putJudge = (role, judge, { actor, rationale = "" } = {}) =>
  call(`/v1/judges/${encodeURIComponent(role)}?rationale=${encodeURIComponent(rationale)}`, {
    method: "PUT",
    body: judge,
    headers: actor ? { "X-Actor": actor } : undefined,
  });

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
