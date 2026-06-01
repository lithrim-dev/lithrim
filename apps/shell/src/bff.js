/* bff.js — the React↔Python bridge client (WS-5-BFF).
   A thin fetch wrapper over the local FastAPI BFF (apps/bff/, the judge-capability
   API v1). Base URL = VITE_BFF_URL when set (e.g. an absolute Tauri/VPC target),
   else "" so requests go through the vite dev proxy (/v1 → :8787). See SPEC §5. */

const BASE = import.meta.env.VITE_BFF_URL ?? "";

async function call(path, { method = "GET", body } = {}) {
  const res = await fetch(BASE + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${method} ${path} → ${res.status}${detail ? `: ${detail}` : ""}`);
  }
  return res.json();
}

/* POST /v1/run-eval — drive one case end-to-end. replay (live=false) is the $0
   default; live=true opts into exactly one real, paid :8002 council call. */
export const runEval = ({ agent = "ws0_default", live = false } = {}) =>
  call("/v1/run-eval", { method: "POST", body: { agent, live } });

export const getCorpus = () => call("/v1/corpus");
export const getOntology = (agent = "ws0_default") =>
  call(`/v1/ontology?agent=${encodeURIComponent(agent)}`);
