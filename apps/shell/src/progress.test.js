/* progress.test.js — GRADE-PROGRESS-1: the module-level batch-grade progress store. The cohort
   grade (POST /v1/cases/grade) is ONE server-side call that runs for minutes; this store is the
   chrome-level in-flight signal the StatusBar chip renders. It lives OUTSIDE React (module state
   + subscribe), so it survives the CostModal closing and artifact-tab switches by construction. */
import { describe, it, expect, vi, afterEach } from "vitest";
import { beginBatch, tickBatch, endBatch, getProgress, subscribeProgress } from "./progress.js";

afterEach(() => endBatch());

describe("grade-progress store (GRADE-PROGRESS-1)", () => {
  it("starts (and resets to) inactive", () => {
    expect(getProgress()).toEqual({ active: false, done: 0, total: null, label: "" });
  });

  it("beginBatch marks one in-flight span — active, done 0, the given total", () => {
    beginBatch({ total: 14 });
    expect(getProgress()).toEqual({ active: true, done: 0, total: 14, label: "grading" });
  });

  it("beginBatch with no total (grade-all: the server counts the cohort) stays total null", () => {
    beginBatch({});
    expect(getProgress()).toMatchObject({ active: true, done: 0, total: null });
  });

  it("tickBatch increments done and returns a NEW snapshot object (useSyncExternalStore contract)", () => {
    beginBatch({ total: 2 });
    const before = getProgress();
    tickBatch();
    expect(getProgress().done).toBe(1);
    expect(getProgress()).not.toBe(before);
  });

  it("tickBatch outside an active span is a no-op", () => {
    tickBatch();
    expect(getProgress()).toEqual({ active: false, done: 0, total: null, label: "" });
  });

  it("endBatch resets to inactive", () => {
    beginBatch({ total: 3 });
    endBatch();
    expect(getProgress()).toEqual({ active: false, done: 0, total: null, label: "" });
  });

  it("subscribers fire on every transition; unsubscribe stops them", () => {
    const spy = vi.fn();
    const off = subscribeProgress(spy);
    beginBatch({ total: 1 });
    tickBatch();
    endBatch();
    expect(spy).toHaveBeenCalledTimes(3);
    off();
    beginBatch({});
    expect(spy).toHaveBeenCalledTimes(3);
  });
});
