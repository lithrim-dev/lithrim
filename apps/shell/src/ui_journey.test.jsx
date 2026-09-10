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
      const key = Object.keys(routes).find((k) => u.includes(k));
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
  it("with no workspace yet the shell opens on a create-or-pick screen and creates one", async () => {
    stubFetch({ "/v1/workspaces": { workspaces: [], active: null } });
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    const picker = await screen.findByTestId("ws-first-run");
    fireEvent.change(screen.getByPlaceholderText("workspace name"), { target: { value: "ragtruth-pilot" } });
    fireEvent.click(screen.getByRole("button", { name: /create workspace/i }));
    await waitFor(() =>
      expect(calls.some((c) => c.url.includes("/v1/workspaces") && c.method === "POST" && String(c.body).includes("ragtruth-pilot"))).toBe(true),
    );
    expect(picker).toBeInTheDocument();
    unmount();
  });

  it("with a workspace present there is no first-run screen", async () => {
    const { unmount } = render(<App mode="shell" setMode={() => {}} />);
    await screen.findByTitle("Switch workspace");
    expect(screen.queryByTestId("ws-first-run")).toBeNull();
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
    fireEvent.click(screen.getByRole("button", { name: /load/i }));
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
