/* bff.test.jsx — A6 / S-BS-18: the React↔BFF binding. Mocks fetch, drives the
   bff.js client (POST /v1/run-eval), and asserts the real-composite shape renders
   through artifact.jsx ReportTab (via the exported ArtifactPane). Guards the React
   side that the Python tests/test_ws5_bff.py round-trip does not cover. */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { runEval, getOntology, listAgents, createAgent, deleteAgent, putJudge, createJudge, validateToken } from "./bff.js";
import { ArtifactPane } from "./artifact.jsx";

// A representative /v1/run-eval response: the S-BS-7 clinical story (reject; one
// active FABRICATED_HISTORY finding; the MED FP grounded-suppressed by the contract).
const COMPOSITE_RESPONSE = {
  case_id: "bench_scribe_v1_inject_condition_1bd0f10dc7b5",
  grade_path: "replay",
  composite: {
    verdict: "reject",
    stage_verdict: "BLOCK",
    score: 1.0,
    active_findings: ["FABRICATED_HISTORY"],
    grounded_adjustments: [
      { flag: "MEDICATION_NOT_IN_TRANSCRIPT", action: "suppress", contract: "med-presence-check/v1", reason: "zidovudine is verbatim in the transcript" },
    ],
  },
  calibration_check: { n_cases: 1, verdict_match_rate: "1/1", status: "PASS", ece: 0.5, caveat: "N=1 diagnostic only" },
};

function mockFetch(body, ok = true, status = ok ? 200 : 500) {
  return vi.fn().mockResolvedValue({ ok, status, json: async () => body, text: async () => JSON.stringify(body) });
}

const paneProps = { width: 440, full: false, tab: "report", setTab: () => {}, onClose: () => {}, onToggleFull: () => {} };

describe("bff.js → ReportTab binding (S-BS-18)", () => {
  it("runEval() POSTs /v1/run-eval and parses the composite", async () => {
    vi.stubGlobal("fetch", mockFetch(COMPOSITE_RESPONSE));
    const result = await runEval({ live: false });

    expect(fetch).toHaveBeenCalledWith(
      "/v1/run-eval",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ agent: "ws0_default", live: false, in_process: false }) }),
    );
    expect(result.composite.verdict).toBe("reject");
    expect(result.composite.active_findings).toContain("FABRICATED_HISTORY");
  });

  it("renders the real composite through ReportTab", async () => {
    vi.stubGlobal("fetch", mockFetch(COMPOSITE_RESPONSE));
    const result = await runEval({ live: false });

    render(<ArtifactPane {...paneProps} runStatus="ready" runResult={result} runError={null} />);

    expect(screen.getAllByText(/Flagged/i).length).toBeGreaterThan(0); // reject banner → "Flagged"
    expect(screen.getByText("Fabricated history")).toBeInTheDocument(); // active finding (readable)
    expect(screen.getByText("Medication not in transcript")).toBeInTheDocument(); // grounded suppression (readable)
    expect(screen.getByText(/1\/1 · PASS/)).toBeInTheDocument(); // calibration_check
  });

  it("surfaces an error when the BFF call fails", async () => {
    vi.stubGlobal("fetch", mockFetch({ detail: "down" }, false));
    await expect(runEval({ live: false })).rejects.toThrow(/run-eval/);
  });

  it("getOntology() hits GET /v1/ontology (read-only)", async () => {
    vi.stubGlobal("fetch", mockFetch({ domain: "clinical", flags: [] }));
    const ont = await getOntology("ws0_default");
    expect(fetch).toHaveBeenCalledWith("/v1/ontology?agent=ws0_default", expect.anything());
    expect(ont.domain).toBe("clinical");
  });
});

// CRUD-1 (D4): the config-plane agent switcher + the blank-slate create/delete client.
describe("CRUD-1 bff.js config-plane client", () => {
  it("listAgents() GETs /v1/agents", async () => {
    vi.stubGlobal("fetch", mockFetch({ agents: ["ws0_default", "eval-1"] }));
    const out = await listAgents();
    expect(fetch).toHaveBeenCalledWith("/v1/agents", expect.anything());
    expect(out.agents).toContain("eval-1");
  });

  it("createAgent() clones the seed dataset/ontology but starts authoring-blank (RUNNABLE)", async () => {
    const seed = {
      name: "ws0_default",
      eval_profile: {
        judges: ["risk_judge"],
        council_config: { disposition: "compose-over-live-v2" },
        ontology_ref: "clinical/1",
        ontology_path: "data/ontology/clinical_v1.json",
        tools: ["presence_check"],
        kb_bindings: {},
        severity_map_ref: "ontology:clinical/1",
      },
      dataset: { case_id: "C", source: "S", baseline: "B", mode: "replay" },
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({ ok: true, status: 200, json: async () => seed, text: async () => "" })
        .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ status: "ok", name: "eval-2" }), text: async () => "" }),
    );
    await createAgent("eval-2");
    // 1) it reads the committed blank-slate template (workspace-independent)
    expect(fetch).toHaveBeenNthCalledWith(1, "/v1/agent/template", expect.anything());
    // 2) it PUTs a blank-but-runnable agent: empty judges/tools, the cloned ontology + Dataset
    const [url, opts] = fetch.mock.calls[1];
    expect(url).toContain("/v1/agent?rationale=");
    expect(opts.method).toBe("PUT");
    const body = JSON.parse(opts.body);
    expect(body.name).toBe("eval-2");
    expect(body.eval_profile.judges).toEqual([]); // authoring-blank
    expect(body.eval_profile.tools).toEqual([]);
    expect(body.eval_profile.ontology_path).toBe("data/ontology/clinical_v1.json"); // cloned
    expect(body.dataset).toEqual(seed.dataset); // BOUND Dataset -> runnable from clean
  });

  it("deleteAgent() DELETEs /v1/agent?name=", async () => {
    vi.stubGlobal("fetch", mockFetch({ status: "deleted", name: "eval-2" }));
    await deleteAgent("eval-2", { rationale: "rm" });
    const [url, opts] = fetch.mock.calls[0];
    expect(opts.method).toBe("DELETE");
    expect(url).toContain("name=eval-2");
  });

  it("S-BS-153: putJudge(role, body, {agent}) PUTs the agent in the query so the server rosters it", async () => {
    vi.stubGlobal("fetch", mockFetch({ status: "ok", role: "risk_judge", rostered: true }));
    await putJudge("risk_judge", { model: "", assigned_flags: ["MISSED_ESCALATION"], validator_refs: [] },
      { actor: "sme@acme", rationale: "assign lens", agent: "demo-clinical" });
    const [url, opts] = fetch.mock.calls[0];
    expect(opts.method).toBe("PUT");
    expect(url).toContain("/v1/judges/risk_judge?");
    expect(url).toContain("agent=demo-clinical");
    expect(url).toContain("rationale=assign+lens");
    expect(opts.headers).toMatchObject({ "X-Actor": "sme@acme" });
  });

  it("S-BS-153: putJudge WITHOUT an agent omits the agent param (no roster add requested)", async () => {
    vi.stubGlobal("fetch", mockFetch({ status: "ok", role: "risk_judge", rostered: false }));
    await putJudge("risk_judge", { model: "", assigned_flags: [], validator_refs: [] }, { rationale: "x" });
    const [url] = fetch.mock.calls[0];
    expect(url).not.toContain("agent=");
  });
});

// PHASE2-C: createJudge mints a NEW first-class judge over the active pack's snapshot.
describe("PHASE2-C bff.js createJudge", () => {
  it("createJudge() POSTs /v1/judges with the authoring body (never a key in the response)", async () => {
    vi.stubGlobal(
      "fetch",
      mockFetch({ role: "escalation_judge", lens_codes: ["MISSED_ESCALATION"], owned_codes: [], model: "grader-gpt4o", bound_roles: ["escalation_judge"], audit_id: "aud-1" }),
    );
    const out = await createJudge({
      role: "escalation_judge",
      lens_codes: ["MISSED_ESCALATION", "WRONG_RESOLUTION"],
      owned_codes: ["MISSED_ESCALATION"],
      model_id: "grader-gpt4o",
      rationale: "support escalations",
    });
    const [url, opts] = fetch.mock.calls[0];
    // rationale rides the query param (mirrors putJudge; the endpoint reads it via Query()).
    expect(url).toContain("/v1/judges?");
    expect(url).toContain("rationale=support+escalations");
    expect(opts.method).toBe("POST");
    const body = JSON.parse(opts.body);
    expect(body).toMatchObject({
      role: "escalation_judge",
      lens_codes: ["MISSED_ESCALATION", "WRONG_RESOLUTION"],
      owned_codes: ["MISSED_ESCALATION"],
      model_id: "grader-gpt4o",
    });
    expect(body).not.toHaveProperty("rationale");  // not in the body — it's the query param
    expect(out.audit_id).toBe("aud-1");
    expect(out).not.toHaveProperty("api_key");
  });

  it("createJudge() omits model_id / role_prompt when unset (spread-only-when-present)", async () => {
    vi.stubGlobal("fetch", mockFetch({ role: "qa_judge", lens_codes: ["WRONG_RESOLUTION"], owned_codes: [], model: "", bound_roles: ["qa_judge"], audit_id: "a2" }));
    await createJudge({ role: "qa_judge", lens_codes: ["WRONG_RESOLUTION"], owned_codes: [], rationale: "qa" });
    const [, opts] = fetch.mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body).not.toHaveProperty("model_id");
    expect(body).not.toHaveProperty("role_prompt");
    expect(body.lens_codes).toEqual(["WRONG_RESOLUTION"]);
  });

  it("createJudge() surfaces a 422 admissibility detail (owner⊄lens / collision)", async () => {
    vi.stubGlobal("fetch", mockFetch({ detail: "owned code not in lens" }, false, 422));
    await expect(createJudge({ role: "x", lens_codes: [], owned_codes: ["Y"], rationale: "r" })).rejects.toThrow(/judges/);
  });
});

// UI-LOGIN-1: the runtime auth gate's signal + validate plumbing in bff.js.
describe("UI-LOGIN-1 bff.js auth gate", () => {
  it("call() on a 401 dispatches the lithrim:auth-required signal (before throwing)", async () => {
    vi.stubGlobal("fetch", mockFetch({ detail: "unauthorized" }, false, 401));
    const spy = vi.fn();
    window.addEventListener("lithrim:auth-required", spy);
    // any call exercising the shared call() wrapper — a 401 must raise the gate signal then throw
    await expect(listAgents()).rejects.toThrow(/agents/);
    window.removeEventListener("lithrim:auth-required", spy);
    expect(spy).toHaveBeenCalled();
  });

  it("validateToken returns false on a 401 (the gate rejected the candidate)", async () => {
    vi.stubGlobal("fetch", mockFetch({ detail: "unauthorized" }, false, 401));
    expect(await validateToken("bad")).toBe(false);
    // it probed the gated route with the candidate as a Bearer header
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toContain("/v1/meta");
    expect(opts.headers).toMatchObject({ Authorization: "Bearer bad" });
  });

  it("validateToken returns true on a 2xx success (the token actually worked)", async () => {
    vi.stubGlobal("fetch", mockFetch({ version: "x" }, true, 200));
    expect(await validateToken("good")).toBe(true);
  });

  it("validateToken returns false on a 5xx (an inconclusive server error must NOT accept the token)", async () => {
    // a transient BFF 500 on the probe is NOT a token confirmation — requiring a 2xx success means
    // an unvalidated token is never stored on a hiccup (the next real call would re-raise the gate).
    vi.stubGlobal("fetch", mockFetch({ detail: "boom" }, false, 500));
    expect(await validateToken("maybe")).toBe(false);
  });
});
