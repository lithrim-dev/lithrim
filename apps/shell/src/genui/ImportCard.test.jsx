/* ImportCard.test.jsx — UI-JOURNEY-1 (B4): the Load verb card over a stubbed service. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ImportCard from "./ImportCard.jsx";

const IMPORTERS = [{ id: "ragtruth_vocabulary", dataset: "ragtruth", adapter: true, files: ["response.jsonl", "source_info.jsonl"], citation: "Niu et al.", license: "MIT", verdict_rule: { ragtruth: "a response is hallucinated iff it carries at least one annotated span" } }];

let calls;
beforeEach(() => {
  calls = [];
  vi.stubGlobal("fetch", vi.fn((url, init) => {
    const u = String(url);
    calls.push({ url: u, body: init && init.body });
    if (u.includes("/v1/importers")) return Promise.resolve({ ok: true, json: async () => ({ importers: IMPORTERS }) });
    if (u.includes("/v1/cases/import")) return Promise.resolve({ ok: true, json: async () => ({ importer: "ragtruth_vocabulary", dataset: "ragtruth", imported: { test: 90, calibration: 90 } }) });
    return Promise.resolve({ ok: true, json: async () => ({}) });
  }));
});

const pickFiles = async () => {
  const inputs = screen.getByTestId("import-cases").querySelectorAll('input[type="file"]');
  fireEvent.change(inputs[0], { target: { files: [new File(['{"id":"1"}\n'], "response.jsonl")] } });
  fireEvent.change(inputs[1], { target: { files: [new File(['{"source_id":"s"}\n'], "source_info.jsonl")] } });
  await waitFor(() => expect(screen.getByTestId("import-load")).not.toBeDisabled());
};

describe("ImportCard", () => {
  it("lists the pack's importers with their provenance and one file input per declared file", async () => {
    render(<ImportCard />);
    await screen.findByTestId("import-importer");
    expect(screen.getByTestId("import-provenance").textContent).toMatch(/Niu et al.*MIT.*annotated span/);
    expect(screen.getByTestId("import-cases").querySelectorAll('input[type="file"]')).toHaveLength(2);
    expect(screen.getByTestId("import-load")).toBeDisabled(); // no files yet
  });

  it("posts the files, the cut size and the splits, and reports exactly what landed", async () => {
    render(<ImportCard importers={IMPORTERS} />);
    await pickFiles();
    fireEvent.change(screen.getByTestId("import-per-task"), { target: { value: "30" } });
    fireEvent.click(screen.getByTestId("import-load"));
    const sent = await waitFor(() => JSON.parse(calls.find((c) => c.url.includes("/v1/cases/import")).body));
    expect(sent).toMatchObject({ importer: "ragtruth_vocabulary", per_task: 30, splits: ["test", "calibration"] });
    expect(Object.keys(sent.files).sort()).toEqual(["response.jsonl", "source_info.jsonl"]);
    expect((await screen.findByTestId("import-result")).textContent).toMatch(/loaded 90 test \+ 90 calibration cases from ragtruth/);
  });

  it("a deselected split is not sent; a service refusal shows as the reason, not a count", async () => {
    vi.stubGlobal("fetch", vi.fn((url, init) => {
      const u = String(url);
      calls.push({ url: u, body: init && init.body });
      if (u.includes("/v1/cases/import")) return Promise.resolve({ ok: false, status: 422, json: async () => ({ detail: "source_info.jsonl missing" }), text: async () => '{"detail":"source_info.jsonl missing"}' });
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }));
    render(<ImportCard importers={IMPORTERS} />);
    await pickFiles();
    fireEvent.click(screen.getByTestId("import-split-calibration"));
    fireEvent.click(screen.getByTestId("import-load"));
    const sent = await waitFor(() => JSON.parse(calls.find((c) => c.url.includes("/v1/cases/import")).body));
    expect(sent.splits).toEqual(["test"]);
    expect((await screen.findByTestId("import-result")).textContent).toMatch(/source_info.jsonl missing/i);
  });

  it("a pack with no importer says so", async () => {
    render(<ImportCard importers={[]} />);
    expect(screen.getByTestId("import-no-importers")).toBeInTheDocument();
  });
});


describe("ImportCard — the calibration split can be graded for a training export", () => {
  it("after a load with a calibration split, the card offers the paid calibration grade", async () => {
    const heard = [];
    const on = (e) => heard.push(e.detail);
    window.addEventListener("lithrim:grade-cohort", on);
    render(<ImportCard importers={IMPORTERS} />);
    await pickFiles();
    fireEvent.click(screen.getByTestId("import-load"));
    fireEvent.click(await screen.findByTestId("import-grade-calibration"));
    expect(heard).toEqual([{ split: "calibration", round: "calibration" }]);
    window.removeEventListener("lithrim:grade-cohort", on);
  });
});
