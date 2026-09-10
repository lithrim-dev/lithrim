/* ui_journey.test.jsx — UI-JOURNEY-1 acceptance (B0): the six verbs from the shell, one
   workspace, no terminal. Each `it` pins one card or control the journey needs; they fail until
   the item that owns them lands (B2 grade trail, B3 workspace, B4 load, B5 scorecard, B7 rounds,
   B8 export, B9 spend). The BFF is a fetch stub routed by URL. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import App from "./app.jsx";
import { STEPS } from "./data.jsx";
import { endBatch } from "./progress.js";
import ScorecardCard from "./genui/ScorecardCard.jsx";

const ok = (body) => Promise.resolve({ ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) });

let calls;
let routes;
function stubFetch(extra = {}) {
  calls = [];
  routes = {
    "/v1/workspaces": { workspaces: [{ name: "default", pack: "_core" }], active: "default" },
    "/v1/jobs?": { jobs: [] },
    "/v1/importers": { importers: [{ id: "ragtruth_vocabulary", dataset: "ragtruth", adapter: true, files: ["response.jsonl", "source_info.jsonl"] }] },
    "/v1/spend": { usd_list_price: 2.05, runs: 180, prompt_tokens: 939258, completion_tokens: 21514 },
    ...extra,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn((url, init) => {
      const u = String(url);
      calls.push({ url: u, method: (init && init.method) || "GET", body: init && init.body });
      const key = Object.keys(routes).filter((k) => u.includes(k)).sort((a, b) => b.length - a.length)[0]; // the most specific route wins
      const hit = key ? routes[key] : {};
      return ok(typeof hit === "function" ? hit(u, init) : hit);
    }),
  );
}

beforeEach(() => {
  endBatch();
  localStorage.clear();
  stubFetch();
});

const openPalette = () => fireEvent.keyDown(window, { key: "k", metaKey: true });

describe("B3 workspace: first run picks or creates one", () => {
  it("with nothing picked yet the shell opens on the picker; creating a workspace posts it and closes the picker", async () => {
    stubFetch({ "/v1/workspaces": { workspaces: [], active: null } });
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    await screen.findByTestId("ws-first-run");
    fireEvent.change(screen.getByPlaceholderText("workspace name"), { target: { value: "ragtruth-pilot" } });
    fireEvent.click(screen.getByRole("button", { name: /create workspace/i }));
    await waitFor(() =>
      expect(calls.some((c) => c.url.includes("/v1/workspaces") && c.method === "POST" && String(c.body).includes("ragtruth-pilot"))).toBe(true),
    );
    await waitFor(() => expect(screen.queryByTestId("ws-first-run")).toBeNull());
    expect(localStorage.getItem("lithrim.workspace.chosen")).toBe("ragtruth-pilot");
    unmount();
  });

  it("picking one of the service's workspaces switches to it and remembers the choice", async () => {
    stubFetch({ "/v1/workspaces": { workspaces: [{ name: "default", pack: "_core" }, { name: "pilot", pack: "_core" }], active: "default" } });
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    await screen.findByTestId("ws-first-run");
    fireEvent.click(screen.getByTestId("ws-pick-pilot"));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/v1/workspace") && c.method === "POST" && String(c.body).includes("pilot"))).toBe(true));
    await waitFor(() => expect(screen.queryByTestId("ws-first-run")).toBeNull());
    expect(localStorage.getItem("lithrim.workspace.chosen")).toBe("pilot");
    unmount();
  });

  it("once a workspace was picked in this browser there is no first-run screen", async () => {
    localStorage.setItem("lithrim.workspace.chosen", "default");
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    await screen.findByTitle("Switch workspace");
    expect(screen.queryByTestId("ws-first-run")).toBeNull();
    unmount();
  });

  it("the palette's Show workspace renders the inventory card from the resources route", async () => {
    localStorage.setItem("lithrim.workspace.chosen", "default");
    stubFetch({ "/v1/workspaces/default/resources": { name: "default", pack: "_core", cases: { total: 180, by_split: { test: 90, calibration: 90 }, importer: "ragtruth_vocabulary" }, runs: 180, jobs: [], pinned_demos: {}, corrections: { records: 0, gold_mismatches: 0 }, exports: [], bindings: { roles: {} } } });
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    openPalette();
    fireEvent.click(await screen.findByTestId("cmdk-item-show-workspace"));
    const card = await screen.findByTestId("workspace-card");
    expect(card.textContent).toMatch(/test 90, calibration 90/);
    unmount();
  });
});

describe("B4 load: the rail has a Load step and the import card speaks importer manifests", () => {
  it("STEPS names a Load step before Run", () => {
    const names = STEPS.map((s) => s.name);
    expect(names).toContain("Load");
    expect(names.indexOf("Load")).toBeLessThan(names.indexOf("Run"));
  });

  it("the import card lists the importers from the service and posts the files with a split", async () => {
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    openPalette();
    fireEvent.click(await screen.findByTestId("cmdk-item-load-dataset"));
    const card = await screen.findByTestId("import-cases");
    expect(card.textContent).toMatch(/ragtruth/);
    const inputs = card.querySelectorAll('input[type="file"]');
    expect(inputs.length).toBe(2);
    fireEvent.change(inputs[0], { target: { files: [new File(['{"id":"1"}\n'], "response.jsonl")] } });
    fireEvent.change(inputs[1], { target: { files: [new File(['{"source_id":"s"}\n'], "source_info.jsonl")] } });
    await waitFor(() => expect(screen.getByTestId("import-load")).not.toBeDisabled());
    fireEvent.click(screen.getByTestId("import-load"));
    await waitFor(() => expect(calls.some((c) => c.url.includes("/v1/cases/import") && c.method === "POST")).toBe(true));
    const sent = JSON.parse(calls.find((c) => c.url.includes("/v1/cases/import")).body);
    expect(sent.importer).toBe("ragtruth_vocabulary");
    expect(sent.splits).toEqual(["test", "calibration"]);
    expect(Object.keys(sent.files).sort()).toEqual(["response.jsonl", "source_info.jsonl"]);
    unmount();
  });
});

describe("B2 grade: the running job is found again after a reload", () => {
  it("on mount a running job for the active agent restores the progress chip and keeps polling", async () => {
    let polls = 0;
    stubFetch({
      "/v1/jobs?": { jobs: [{ job_id: "job-1", agent: "ws0_default", status: "running", done: 4, total: 9, round: "before" }] },
      "/v1/jobs/job-1": () => (++polls < 2 ? { job_id: "job-1", status: "running", done: 6, total: 9 } : { job_id: "job-1", status: "done", done: 9, total: 9, result: { matrix: [], summary: {}, scorecard: { cases: [] } } }),
    });
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    const chip = await screen.findByTestId("grade-progress");
    expect(chip.textContent).toMatch(/4\s*\/\s*9|grading/);
    await waitFor(() => expect(screen.queryByTestId("grade-progress")).toBeNull(), { timeout: 8000 });
    expect(polls).toBeGreaterThanOrEqual(2);
    unmount();
  }, 10000);

  it("an interrupted job offers resume instead of vanishing", async () => {
    stubFetch({
      "/v1/jobs?": { jobs: [{ job_id: "job-2", agent: "ws0_default", status: "interrupted", done: 4, total: 9, round: "before" }] },
    });
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    const resume = await screen.findByTestId("job-resume");
    fireEvent.click(resume);
    await waitFor(() =>
      expect(calls.some((c) => c.url.includes("/v1/cases/grade") && c.method === "POST" && String(c.body).includes('"resume":"job-2"'))).toBe(true),
    );
    unmount();
  });
});

describe("B5 / B7 / B8 scorecard: both vocabularies, rounds, re-grade and export controls", () => {
  const perTask = [
    { task: "Data2txt", n: 30, P: 81.8, R: 94.7, F1: 87.8, span_P: 54.1, span_R: 71.4, span_F1: 61.5, refused: 0 },
    { task: "OVERALL", n: 90, P: 66.7, R: 84.8, F1: 74.7, span_P: 53.8, span_R: 71.4, span_F1: 61.4, refused: 3 },
  ];
  const vocabulary = {
    dataset: "ragtruth",
    verdict_rule: { ragtruth: "a response is hallucinated iff it carries at least one annotated span", lithrim: "a case is BLOCK iff at least one Tier-1 finding stands after the floor" },
  };
  const perCode = [{ code: "SOURCE_CONTRADICTION", dataset_terms: ["Evident Conflict", "Subtle Conflict"], tp: 7, fp: 2, fn: 16, P: 77.8, R: 30.4, F1: 43.8 }];

  it("renders the per-task table with span columns, the per-code dataset terms and the verdict rule", () => {
    render(<ScorecardCard cases={[]} n_cases={90} n_labeled={90} per_task={perTask} per_code={perCode} vocabulary={vocabulary} round="before" job_id="job-1" />);
    const table = screen.getByTestId("scorecard-per-task");
    expect(table.textContent).toMatch(/Data2txt/);
    expect(table.textContent).toMatch(/61\.4/);
    expect(screen.getByTestId("scorecard-per-code").textContent).toMatch(/Evident Conflict/);
    expect(screen.getByTestId("scorecard-verdict-rule").textContent).toMatch(/annotated span/);
    expect(screen.getByTestId("scorecard-verdict-rule").textContent).toMatch(/Tier-1/);
  });

  it("a before round with pinned demos offers the paid re-grade and the $0 replay labelled as not a measurement", () => {
    const onRegrade = vi.fn();
    const onReplay = vi.fn();
    render(<ScorecardCard cases={[]} n_cases={90} n_labeled={90} per_task={perTask} round="before" job_id="job-1" pinned_demos={{ role: "ragtruth_detector", n: 4, graded: 0.67 }} onRegrade={onRegrade} onReplay={onReplay} />);
    fireEvent.click(screen.getByTestId("regrade-pinned"));
    expect(onRegrade).toHaveBeenCalled();
    const replay = screen.getByTestId("replay-zero");
    expect(replay.textContent).toMatch(/not a measurement/i);
    fireEvent.click(replay);
    expect(onReplay).toHaveBeenCalled();
    expect(screen.getByTestId("scorecard-round").textContent).toMatch(/before/);
  });

  it("before and after rounds sit side by side when a comparison is given", () => {
    render(<ScorecardCard cases={[]} n_cases={90} n_labeled={90} per_task={perTask} round="after" job_id="job-2" compare={{ round: "before", per_task: [{ task: "OVERALL", F1: 65.9, span_F1: 53.2 }] }} />);
    const table = screen.getByTestId("scorecard-per-task");
    expect(table.textContent).toMatch(/65\.9/);
    expect(table.textContent).toMatch(/74\.7/);
  });

  it("the export control posts the job to /v1/export and shows the row count", async () => {
    const onExport = vi.fn().mockResolvedValue({ rows: 62, tiers: { "judge-only": 54, "floor-proved": 8 }, name: "export_test.jsonl" });
    render(<ScorecardCard cases={[]} n_cases={90} n_labeled={90} per_task={perTask} round="after" job_id="job-2" onExport={onExport} />);
    fireEvent.click(screen.getByTestId("export-corpus"));
    await waitFor(() => expect(onExport).toHaveBeenCalledWith("job-2", expect.anything()));
    expect((await screen.findByTestId("export-result")).textContent).toMatch(/62/);
  });
});

describe("B9 spend: the running line", () => {
  it("the chrome shows the list-price spend for the active agent", async () => {
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    const line = await screen.findByTestId("spend-line");
    expect(line.textContent).toMatch(/\$2\.05/);
    unmount();
  });
});


describe("B7 rounds through the shell", () => {
  it("a finished before round's card offers the re-grade; confirming posts round=after on the same split", async () => {
    localStorage.setItem("lithrim.workspace.chosen", "default");
    stubFetch({
      "/v1/jobs/job-b/scorecard": { job_id: "job-b", round: "before", per_task: [{ task: "OVERALL", n: 3, P: 50, R: 50, F1: 50, span_P: 50, span_R: 50, span_F1: 50, refused: 0 }], per_code: [], vocabulary: { dataset: "ragtruth", verdict_rule: { ragtruth: "x", lithrim: "y" } }, unlocated: [], pinned_demos: { ragtruth_detector: { demos: 4, graded: 0.67 } } },
      "/v1/cases/grade": { job_id: "job-a", status: "running", done: 0, total: 3 },
      "/v1/jobs/job-a/scorecard": { job_id: "job-a", round: "after", per_task: [{ task: "OVERALL", n: 3, F1: 60, span_F1: 55 }], per_code: [], vocabulary: {}, unlocated: [], compare: { job_id: "job-b", round: "before", per_task: [{ task: "OVERALL", F1: 50, span_F1: 50 }] } },
      "/v1/jobs/job-a": { job_id: "job-a", status: "done", done: 3, total: 3, round: "after", split: "test", result: { matrix: [], summary: {}, scorecard: { cases: [] } } },
    });
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    await screen.findByTitle("Switch workspace");
    fireEvent(window, new CustomEvent("lithrim:job-done", { detail: { job: { job_id: "job-b", round: "before", split: "test", status: "done", result: { matrix: [], summary: {}, scorecard: { cases: [] } } } } }));
    const regrade = await screen.findByTestId("regrade-pinned");
    expect(screen.getByTestId("scorecard-pinned").textContent).toMatch(/ragtruth_detector: 4 demos/);
    fireEvent.click(regrade);
    expect(await screen.findByText(/Grade the test split again with the pinned demos \(paid\)\?/)).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: /Grade again with the pinned demos \(paid\)/ }).pop()); // the modal's confirm, not the card's control
    await waitFor(() => {
      const sent = calls.find((c) => c.url.includes("/v1/cases/grade") && c.method === "POST");
      expect(sent && JSON.parse(sent.body)).toMatchObject({ round: "after", split: "test", in_process: true, background: true });
    });
    // the after card sits beside the before round
    await waitFor(() => expect(screen.getAllByTestId("per-task-OVERALL").length).toBe(2), { timeout: 8000 });
    const table = screen.getAllByTestId("per-task-OVERALL").pop(); // the after card, beside the before one
    expect(table.textContent).toMatch(/60\.0/);
    expect(table.textContent).toMatch(/50\.0/);
    unmount();
  }, 12000);

  it("the $0 replay posts the free grade path tagged replay and the card says it is not a measurement", async () => {
    localStorage.setItem("lithrim.workspace.chosen", "default");
    stubFetch({
      "/v1/jobs/job-b/scorecard": { job_id: "job-b", round: "before", per_task: [{ task: "OVERALL", n: 3 }], per_code: [], vocabulary: {}, unlocated: [] },
      "/v1/cases/grade": { job_id: "job-r", status: "running", done: 0, total: 3 },
      "/v1/jobs/job-r/scorecard": { job_id: "job-r", round: "replay", per_task: [{ task: "OVERALL", n: 3 }], per_code: [], vocabulary: {}, unlocated: [] },
      "/v1/jobs/job-r": { job_id: "job-r", status: "done", done: 3, total: 3, round: "replay", split: "test", result: { matrix: [], summary: { grade_path: "replay" }, scorecard: { cases: [] } } },
    });
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    await screen.findByTitle("Switch workspace");
    fireEvent(window, new CustomEvent("lithrim:job-done", { detail: { job: { job_id: "job-b", round: "before", split: "test", status: "done", result: { matrix: [], summary: {}, scorecard: { cases: [] } } } } }));
    fireEvent.click(await screen.findByTestId("replay-zero"));
    await waitFor(() => {
      const sent = calls.find((c) => c.url.includes("/v1/cases/grade") && c.method === "POST");
      expect(sent && JSON.parse(sent.body)).toMatchObject({ round: "replay", split: "test", live: false, in_process: false });
    });
    expect(screen.queryByText(/paid\)\?/)).toBeNull(); // no cost gate on the free path
    expect(await screen.findByTestId("scorecard-replay-note", {}, { timeout: 8000 })).toBeInTheDocument();
    unmount();
  }, 12000);
});


describe("B10b configure from the shell: the reviewer builder and editor open from the palette", () => {
  it("Create a reviewer renders the builder card; Edit reviewer <role> renders that role's editor", async () => {
    localStorage.setItem("lithrim.workspace.chosen", "default");
    stubFetch({
      "/v1/agent?": { name: "ws0_default", eval_profile: { ontology_ref: "x/1", judges: ["risk_judge"], council_config: { reviewer_roster: ["ragtruth_detector"] } }, dataset: { case_id: "c1" } },
      "/v1/ontology": { flags: [{ flag: "SOURCE_CONTRADICTION" }], severity_map: {} },
      "/v1/models": { models: [] },
      "/v1/judges/risk_judge": { role: "risk_judge", assigned_flags: [], available_flags: [], base_prompt: "p", rendered_prompt: "p" },
    });
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    await screen.findByTitle("Switch workspace");
    openPalette();
    fireEvent.click(await screen.findByTestId("cmdk-item-create-judge"));
    expect((await screen.findAllByText(/Create reviewer/)).length).toBeGreaterThan(0);
    await waitFor(() => expect(screen.getAllByTestId("judge-import").length).toBeGreaterThan(0));
    openPalette();
    expect(await screen.findByTestId("cmdk-item-edit-judge-ragtruth_detector")).toBeInTheDocument(); // a rostered authored role, not only the pack's judges
    fireEvent.click(screen.getByTestId("cmdk-item-edit-judge-risk_judge"));
    await waitFor(() => expect(screen.getAllByText(/Loading reviewer|Judge · risk_judge/).length).toBeGreaterThan(0));
    unmount();
  });
});


describe("KPI-PINS-1: KPI contracts from the shell", () => {
  it("the palette's Add a check or KPI contract renders the contract builder with the KPI types", async () => {
    localStorage.setItem("lithrim.workspace.chosen", "default");
    stubFetch({ "/v1/grounding-contract/types": { contract_types: ["field_in_set", "kpi_threshold", "value_grounding"], pack: "_core" } });
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    await screen.findByTitle("Switch workspace");
    openPalette();
    fireEvent.click(await screen.findByTestId("cmdk-item-add-contract"));
    expect((await screen.findAllByText("Fact-check")).length).toBeGreaterThan(0);
    expect(screen.getByLabelText("params json")).toBeInTheDocument();
    unmount();
  });
});


describe("FT-FROM-SHELL-1: grade the calibration split for a training export", () => {
  it("the palette entry opens the cost confirm and posts split=calibration as round=calibration", async () => {
    localStorage.setItem("lithrim.workspace.chosen", "default");
    stubFetch({ "/v1/cases/grade": { job_id: "job-c", status: "running", done: 0, total: 90 } });
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    await screen.findByTitle("Switch workspace");
    openPalette();
    fireEvent.click(await screen.findByTestId("cmdk-item-grade-calibration"));
    expect(await screen.findByText(/Grade the calibration split \(paid\)\?/)).toBeInTheDocument();
    expect(screen.getByText(/so a training export has graded rows to draw on\. The test split is not touched/)).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: /Grade the calibration split \(paid\)/ }).pop());
    await waitFor(() => {
      const sent = calls.find((c) => c.url.includes("/v1/cases/grade") && c.method === "POST");
      expect(sent && JSON.parse(sent.body)).toMatchObject({ split: "calibration", round: "calibration", in_process: true });
    });
    unmount();
  });
});
