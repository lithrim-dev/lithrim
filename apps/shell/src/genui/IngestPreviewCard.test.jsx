/* IngestPreviewCard — CE-INGEST-FRONTDOOR-1: the upload preview card, including failure-recovery
   (a non-converging preview renders a rules box + Retry, never a dead end). */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import IngestPreviewCard from "./IngestPreviewCard.jsx";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }));
});

describe("IngestPreviewCard", () => {
  it("renders the failure-recovery UI (message + rules box + retry) when preview errors", () => {
    render(
      <IngestPreviewCard
        error="The extractor did not converge to a clean 1-case transform; nothing pinned."
        raw='{"episodes":[{}]}'
        filename="custom_support_trace.json"
        agent="ws0_default"
      />,
    );
    // the error headline names the file and frames it as recoverable, NOT a dead end
    expect(screen.getByText(/Couldn't map/i)).toBeInTheDocument();
    expect(screen.getByText(/did not converge/i)).toBeInTheDocument();
    // the recovery affordances: the field-mapping rules box + a Retry button
    expect(screen.getByTestId("ingest-rules")).toBeInTheDocument();
    expect(screen.getByTestId("ingest-retry")).toBeInTheDocument();
    // a failed preview has nothing to approve
    expect(screen.queryByTestId("ingest-approve")).not.toBeInTheDocument();
  });

  it("renders the extracted cases + approve when the preview succeeded", () => {
    render(
      <IngestPreviewCard
        fmt="json"
        count={3}
        sample_cases={[{ case_id: "ep-1001", response: "a reply", context: "a question" }]}
        template="$map: $ resource.episodes"
        raw='{"episodes":[{},{},{}]}'
        filename="custom_support_trace.json"
        agent="ws0_default"
      />,
    );
    expect(screen.getByText(/3 cases from JSON/i)).toBeInTheDocument();
    expect(screen.getByText("ep-1001")).toBeInTheDocument();
    expect(screen.getByTestId("ingest-approve")).toBeInTheDocument();
    // the generated JUTE template is surfaced for verification
    expect(screen.getByTestId("ingest-template")).toBeInTheDocument();
  });
});
