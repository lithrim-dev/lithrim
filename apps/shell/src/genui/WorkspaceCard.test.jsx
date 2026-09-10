/* WorkspaceCard.test.jsx — UI-JOURNEY-1 (B3): the workspace inventory card. */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import WorkspaceCard from "./WorkspaceCard.jsx";

const RES = {
  name: "ragtruth-pilot", pack: "_core", agent: "ws0_default",
  cases: { total: 180, by_split: { test: 90, calibration: 90 }, importer: "ragtruth_vocabulary" },
  runs: 180,
  jobs: [{ job_id: "job-1", round: "before", status: "done", done: 90, total: 90 }],
  pinned_demos: { ragtruth_detector: { demos: 4, graded: 0.67 } },
  corrections: { records: 120, gold_mismatches: 62 },
  exports: [{ name: "export_test.jsonl", rows: 62 }],
  bindings: { roles: { ragtruth_detector: { provider: "azure", model: "gpt-4.1" } } },
  arm_manifest: { model: "azure/gpt-4.1", azure_model_version: "2025-04-14" },
};

describe("WorkspaceCard", () => {
  it("names everything the loop left behind", () => {
    render(<WorkspaceCard {...RES} />);
    expect(screen.getByTestId("workspace-card").textContent).toMatch(/ragtruth-pilot/);
    expect(screen.getByTestId("workspace-cases").textContent).toMatch(/180.*test 90, calibration 90.*ragtruth_vocabulary/);
    expect(screen.getByTestId("workspace-jobs").textContent).toMatch(/job-1 · before · done 90\/90/);
    expect(screen.getByTestId("workspace-demos").textContent).toMatch(/ragtruth_detector: 4 demos, held-out graded 0.67/);
    expect(screen.getByTestId("workspace-corrections").textContent).toMatch(/120 records, 62 gold mismatches/);
    expect(screen.getByTestId("workspace-exports").textContent).toMatch(/export_test.jsonl \(62 rows\)/);
    expect(screen.getByTestId("workspace-bindings").textContent).toMatch(/azure\/gpt-4.1/);
    expect(screen.getByTestId("workspace-arm").textContent).toMatch(/served 2025-04-14/);
  });

  it("an empty output is an honest empty state", () => {
    render(<WorkspaceCard />);
    expect(screen.getByTestId("workspace-card-empty").textContent).toMatch(/No workspace loaded yet/);
  });

  it("a fresh workspace says none yet, never a fabricated inventory", () => {
    render(<WorkspaceCard name="fresh" pack="_core" cases={{ total: 0, by_split: {} }} runs={0} />);
    expect(screen.getByTestId("workspace-jobs").textContent).toMatch(/none yet/);
    expect(screen.getByTestId("workspace-demos").textContent).toMatch(/none pinned/);
    expect(screen.getByTestId("workspace-arm").textContent).toMatch(/no arm manifest/);
  });
});
