/* IngestPreviewCard.casechange.test.jsx — KPI-PINS-1: an approved upload announces the corpus
   change, so the rail's Load step ticks without a reload. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../bff.js", () => ({
  ingestPreview: vi.fn(),
  ingestCommit: vi.fn().mockResolvedValue({ count: 4, mapping_id: null, native: true }),
}));

import IngestPreviewCard from "./IngestPreviewCard.jsx";

describe("IngestPreviewCard — approve announces the corpus change", () => {
  it("dispatches lithrim:cases-changed with the commit result", async () => {
    const heard = [];
    const on = (e) => heard.push(e.detail);
    window.addEventListener("lithrim:cases-changed", on);
    render(<IngestPreviewCard fmt="otel" count={4} sample_cases={[{ case_id: "otel_a" }]} raw="{}" filename="t.json" />);
    fireEvent.click(screen.getByTestId("ingest-approve"));
    await waitFor(() => expect(heard).toHaveLength(1));
    expect(heard[0]).toMatchObject({ count: 4 });
    window.removeEventListener("lithrim:cases-changed", on);
  });
});
