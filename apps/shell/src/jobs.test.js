/* jobs.test.js — UI-JOURNEY-1 (B2): the poller survives dropped polls and reports the end state. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { pollJob, followJob, restoreJobs, stopFollowing } from "./jobs.js";
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

/* JOB-POLLER-1: one poller per job, and none left running for an agent nobody is looking at.
   Two callers can reach the same job (the tab that started it and the mount-time restore), and
   the panes re-mount on an agent switch; each extra poller re-entered beginBatch/endBatch, so
   the chip flickered, one poller's endBatch cleared another's progress, and a poller for the
   previous agent kept polling and could announce ITS job into the new agent's chrome. */
describe("JOB-POLLER-1: one poller per job", () => {
  it("a second follow of the same job joins the first instead of starting another", async () => {
    responses = [
      { job_id: "j", status: "running", done: 1, total: 3 },
      { job_id: "j", status: "done", done: 3, total: 3 },
    ];
    const heard = [];
    const onDone = (e) => heard.push(e.detail.job.job_id);
    window.addEventListener("lithrim:job-done", onDone);
    const a = followJob({ job_id: "j", total: 3 }, { interval: 1 });
    const b = followJob({ job_id: "j", total: 3 }, { interval: 1 });
    const [ja, jb] = await Promise.all([a, b]);
    window.removeEventListener("lithrim:job-done", onDone);
    expect(ja).toBe(jb); // the same record: one poller, one result
    expect(responses.length).toBe(0); // only the one poller's polls were spent
    expect(heard).toEqual(["j"]); // announced once, not twice
    expect(getProgress().active).toBe(false);
  });

  it("a finished job can be followed again later (the registry does not leak)", async () => {
    responses = [{ job_id: "j", status: "done", done: 1, total: 1 }];
    await followJob({ job_id: "j", total: 1 }, { interval: 1 });
    responses = [{ job_id: "j", status: "done", done: 1, total: 1 }];
    await followJob({ job_id: "j", total: 1 }, { interval: 1 });
    expect(responses.length).toBe(0);
  });

  it("stopFollowing ends a poller without announcing its job or clobbering the chip", async () => {
    responses = [
      { job_id: "old", status: "running", done: 1, total: 9 },
      { job_id: "old", status: "done", done: 9, total: 9 },
    ];
    const heard = [];
    const onDone = (e) => heard.push(e.detail.job.job_id);
    window.addEventListener("lithrim:job-done", onDone);
    const p = followJob({ job_id: "old", agent: "agent_a", total: 9 }, { interval: 1 });
    stopFollowing((st) => st.agent !== "agent_b");
    await p;
    window.removeEventListener("lithrim:job-done", onDone);
    expect(heard).toEqual([]); // the old agent's job never lands in the new agent's chrome
    expect(getProgress().active).toBe(false);
  });

  it("restoreJobs for a new agent stops the previous agent's poller", async () => {
    responses = [
      { job_id: "old", status: "running", done: 1, total: 9 },
      { job_id: "old", status: "running", done: 2, total: 9 },
      { jobs: [] },
    ];
    const p = followJob({ job_id: "old", agent: "agent_a", total: 9 }, { interval: 1 });
    await restoreJobs("agent_b", { interval: 1 });
    await p;
    expect(getProgress().active).toBe(false);
  });
});
