/* jobs.test.js — UI-JOURNEY-1 (B2): the poller survives dropped polls and reports the end state. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { pollJob, followJob, restoreJobs } from "./jobs.js";
import { getProgress, endBatch, markInterrupted } from "./progress.js";

let responses;
beforeEach(() => {
  endBatch();
  markInterrupted(null);
  responses = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url) => {
      const next = responses.shift();
      if (next instanceof Error) return Promise.reject(next);
      return Promise.resolve({ ok: true, status: 200, json: async () => next, text: async () => JSON.stringify(next) });
    }),
  );
});

describe("pollJob", () => {
  it("absorbs failed polls with backoff and returns the finished record", async () => {
    responses = [new Error("socket hang up"), { job_id: "j", status: "running", done: 1, total: 2 }, new Error("reset"), { job_id: "j", status: "done", done: 2, total: 2 }];
    const seen = [];
    const job = await pollJob("j", { interval: 1, onProgress: (j) => seen.push(j.done) });
    expect(job.status).toBe("done");
    expect(seen).toEqual([1, 2]);
  });

  it("gives up after more than `retries` consecutive failures", async () => {
    responses = [new Error("a"), new Error("b"), new Error("c")];
    await expect(pollJob("j", { interval: 1, retries: 2 })).rejects.toThrow(/c/);
  });
});

describe("followJob / restoreJobs", () => {
  it("drives the chip, announces a finished job on the bridge, and clears the chip", async () => {
    responses = [{ job_id: "j", status: "running", done: 1, total: 3 }, { job_id: "j", status: "done", done: 3, total: 3, result: { scorecard: {} } }];
    const heard = [];
    window.addEventListener("lithrim:job-done", (e) => heard.push(e.detail.job.job_id));
    const p = followJob({ job_id: "j", total: 3 }, { interval: 1 });
    expect(getProgress().active).toBe(true);
    expect(getProgress().job).toBe("j");
    await p;
    expect(getProgress().active).toBe(false);
    expect(heard).toEqual(["j"]);
  });

  it("a job the server reports interrupted stays on the chrome as resumable", async () => {
    responses = [{ jobs: [{ job_id: "j2", agent: "a", status: "interrupted", done: 4, total: 9 }] }];
    await restoreJobs("a", { interval: 1 });
    expect(getProgress().interrupted).toMatchObject({ job_id: "j2", done: 4, total: 9 });
    expect(getProgress().active).toBe(false);
  });

  it("is offline-safe: a failed list is not an error", async () => {
    responses = [new Error("offline")];
    await expect(restoreJobs("a")).resolves.toBeNull();
  });
});


describe("restoreJobs follows grade jobs only (OPTIMIZE-JOB-1)", () => {
  it("a running calibration job is left to the judge editor, not put on the grade chip", async () => {
    responses = [{ jobs: [{ job_id: "o1", kind: "optimize", role: "r", agent: "a", status: "running" }] }];
    await expect(restoreJobs("a", { interval: 1 })).resolves.toBeNull();
    expect(getProgress().active).toBe(false);
    expect(getProgress().interrupted).toBeNull();
  });
});
