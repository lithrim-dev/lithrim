/* reportRead.test.js — NARRATIVE-LAYER-1: the plain-language "read" strings are PURE functions
   of the real payloads (scorecard, case result, votes). Every sentence is computed; a missing
   field degrades (sentence omitted / null), never invented. Honesty branches pinned: a genuine
   defect cleared is said loudly (no trust line), post<=pre never says "climbs", no floor
   activity -> no band. No em/en dashes anywhere. */
import { describe, it, expect } from "vitest";
import { scorecardRead, caseRead, votesRead } from "./reportRead.js";

const mkCases = () =>
  [...Array(3).fill("PASS"), ...Array(7).fill("BLOCK"), ...Array(4).fill("WARN")]
    .map((v, i) => ({ case_id: `c${i}`, verdict: v, labeled: i !== 13 }));

const SCORECARD = {
  cases: mkCases(),
  n_cases: 14, n_labeled: 13,
  flag: { tp: 11, fp: 21, fn: 3, precision: 0.34, recall: 0.79 },
  by_judge: [
    { judge_role: "r1", model: "gpt-4.1", n: 13, matches_gold: 5, misses: 4, over_flags: 4 },
    { judge_role: "r2", model: "claude", n: 13, matches_gold: 6, misses: 3, over_flags: 4 },
    { judge_role: "r3", model: "gemini", n: 13, matches_gold: 4, misses: 5, over_flags: 4 },
  ],
  floor: {
    cleared: 2, enforced: 8, inconclusive: 1, gold_defect_clears: [],
    verdict_accuracy_pre_floor: 0.39, verdict_accuracy_post_floor: 0.54,
    verdict_accuracy_no_floor: 0.39,
  },
};

describe("scorecardRead — the cohort read", () => {
  it("composes the full read from a real run payload (floor lifts 39% -> 54%)", () => {
    const r = scorecardRead(SCORECARD);
    expect(r.text).toBe(
      "3 of 14 notes passed clean, 7 were flagged, 4 need a human look. "
      + "On their own, the three reviewers matched the answer key just 39% of the time: they disagree and they over-flag. "
      + "That noise is expected, it is why the floor exists. "
      + "The deterministic floor enforced 8 real defects the reviewers missed, cleared 2 false alarms, and cleared zero genuine defects. "
      + "The floor lifted verdict accuracy from 39% to 54%. "
      + "Both sides of that number use the same scoring rule, so the lift is the floor's alone.",
    );
    expect(r.hero).toEqual({ pre: 39, post: 54, basis: "floor" });
    expect(r.trust).toBe(true);
  });

  it("READ-ATTRIB-1: an idle floor is credited with nothing, however far pre sits from post", () => {
    // the observed 2026-07-21 batch: council 85%, rescore 69% either side of an idle floor.
    const r = scorecardRead({
      ...SCORECARD,
      floor: {
        ...SCORECARD.floor,
        verdict_accuracy_pre_floor: 0.85, verdict_accuracy_post_floor: 0.69,
        verdict_accuracy_no_floor: 0.69,
      },
    });
    expect(r.text).toMatch(/The floor changed no verdict here: accuracy is 69% with it and without it\./);
    expect(r.text).toMatch(/moves accuracy from 85% to 69%\. That shift is the scoring rule, not the floor\./);
    expect(r.text).not.toMatch(/The gap is the floor/);
    expect(r.text).not.toMatch(/climbs/);
    expect(r.hero).toEqual({ pre: 69, post: 69, basis: "floor" });
  });

  it("READ-ATTRIB-1: a floor that HURT accuracy says so and kills the trust line", () => {
    const r = scorecardRead({
      ...SCORECARD,
      floor: {
        ...SCORECARD.floor,
        verdict_accuracy_pre_floor: 0.5, verdict_accuracy_post_floor: 0.42,
        verdict_accuracy_no_floor: 0.61,
      },
    });
    expect(r.text).toMatch(/The floor moved verdict accuracy from 61% down to 42%, investigate before trusting this run\./);
    expect(r.trust).toBe(false);
  });

  it("READ-ATTRIB-1: with no counterfactual the gap is stated but never attributed", () => {
    const { verdict_accuracy_no_floor: _drop, ...legacy } = SCORECARD.floor;
    const r = scorecardRead({ ...SCORECARD, floor: legacy });
    expect(r.text).toMatch(/Verdict accuracy moves from 39% to 54%\. This run cannot attribute that gap to the floor\./);
    expect(r.text).not.toMatch(/The gap is the floor/);
    expect(r.hero).toEqual({ pre: 39, post: 54, basis: "mixed" });
  });

  it("READ-ATTRIB-1: zero verdict over-flags never claims over-flagging; unmatched codes read as mistyping", () => {
    const r = scorecardRead({
      ...SCORECARD,
      flag: { ...SCORECARD.flag, fp: 21 },
      by_judge: SCORECARD.by_judge.map((j) => ({ ...j, over_flags: 0 })),
    });
    expect(r.text).not.toMatch(/they over-flag/);
    expect(r.text).toMatch(/they raise codes the answer key does not have/);
  });

  it("HONESTY: a genuine defect cleared is said loudly and kills the trust line", () => {
    const r = scorecardRead({
      ...SCORECARD,
      floor: { ...SCORECARD.floor, gold_defect_clears: [{ case_id: "c9", code: "FABRICATED_CLAIM" }] },
    });
    expect(r.text).toMatch(/cleared 1 genuine defect, investigate before trusting this run/);
    expect(r.text).not.toMatch(/zero genuine defects/);
    expect(r.trust).toBe(false);
  });

  it("HONESTY: post <= pre never says climbs and drops the gap claim", () => {
    const { verdict_accuracy_no_floor: _drop, ...legacy } = SCORECARD.floor;
    const r = scorecardRead({
      ...SCORECARD,
      floor: { ...legacy, verdict_accuracy_pre_floor: 0.5, verdict_accuracy_post_floor: 0.42 },
    });
    expect(r.text).toMatch(/Verdict accuracy moves from 50% to 42%\./);
    expect(r.text).not.toMatch(/climbs/);
    expect(r.text).not.toMatch(/The gap is the floor/);
  });

  it("returns null with no floor block, and with an all-zero floor", () => {
    expect(scorecardRead({ ...SCORECARD, floor: null })).toBeNull();
    expect(scorecardRead({})).toBeNull();
    expect(scorecardRead({
      ...SCORECARD,
      floor: { cleared: 0, enforced: 0, inconclusive: 3, gold_defect_clears: [] },
    })).toBeNull();
  });

  it("spells reviewer counts 2..9, keeps 10+ numeric, degrades to 'the reviewers' with no by_judge", () => {
    const many = scorecardRead({ ...SCORECARD, by_judge: Array.from({ length: 12 }, (_, i) => ({ judge_role: `r${i}`, matches_gold: i, over_flags: 1 })) });
    expect(many.text).toMatch(/the 12 reviewers matched/);
    const none = scorecardRead({ ...SCORECARD, by_judge: [] });
    expect(none.text).toMatch(/the reviewers matched the answer key just 39%/);
    expect(none.hero).toEqual({ pre: 39, post: 54, basis: "floor" });
  });

  it("degrades with no pre/post accuracy: no hero, no accuracy sentences, floor sentence stays", () => {
    const r = scorecardRead({
      ...SCORECARD,
      floor: { cleared: 2, enforced: 8, inconclusive: 1, gold_defect_clears: [] },
    });
    expect(r.hero).toBeNull();
    expect(r.text).not.toMatch(/%/);
    expect(r.text).toMatch(/The deterministic floor enforced 8 real defects/);
  });

  it("never emits an em or en dash", () => {
    expect(/[—–]/.test(scorecardRead(SCORECARD).text)).toBe(false);
  });
});

describe("caseRead — the single-case read", () => {
  it("floor enforced + no judge blocked: the wobble story, defects humanized", () => {
    const text = caseRead({
      votes: [
        { role: "risk_judge", vote: "PASS", confidence: 1.0 },
        { role: "policy_judge", vote: "WARN", confidence: 0.44 },
        { role: "faithfulness_judge", vote: "WARN", confidence: 0.4 },
      ],
      floorBlocks: [
        { flag: "DISSENT_ERASURE", contract_type: "value_presence" },
        { flag: "MEDICATION_NOT_IN_TRANSCRIPT", contract_type: "record_presence" },
      ],
      verdict: "BLOCK",
    });
    expect(text).toBe(
      "The reviewers split: Risk passed it outright at full confidence, Policy and Faithfulness were only uncertain. "
      + "On the judges alone this note slips through. "
      + "The floor didn't hesitate: 2 deterministic fact-checks found Dissent erasure and Medication not in transcript, each pinned to the transcript. "
      + "That is why it is flagged. The judges wobbled, the floor held.",
    );
  });

  it("floor enforced + a judge blocked: independent confirmation, not a rescue story", () => {
    const text = caseRead({
      votes: [
        { role: "risk_judge", vote: "PASS", confidence: 1.0 },
        { role: "erasure_judge", vote: "BLOCK", confidence: 0.9 },
      ],
      floorBlocks: [{ flag: "DISSENT_ERASURE" }],
      verdict: "BLOCK",
    });
    expect(text).toBe(
      "The reviewers split: Risk passed it outright at full confidence, Erasure flagged it. "
      + "The floor independently confirmed it: Dissent erasure, pinned to the transcript.",
    );
  });

  it("floor cleared only: the disproof is mentioned (accepts judge_role keys)", () => {
    const text = caseRead({
      votes: [
        { judge_role: "risk_judge", vote: "BLOCK", confidence: 0.9 },
        { judge_role: "policy_judge", vote: "BLOCK", confidence: 0.9 },
      ],
      floorClears: [{ flag: "FABRICATED_CLAIM" }, { flag: "FABRICATED_CLAIM" }],
      verdict: "PASS",
    });
    expect(text).toBe("Both reviewers flagged it. The floor disproved 2 false alarms: Fabricated claim.");
  });

  it("no floor events: a one-sentence judge summary plus the result", () => {
    const text = caseRead({
      votes: [
        { role: "risk_judge", vote: "PASS", confidence: 1.0 },
        { role: "policy_judge", vote: "WARN", confidence: 0.5 },
      ],
      verdict: "WARN",
    });
    expect(text).toBe("The reviewers split: Risk passed it outright at full confidence, Policy was only uncertain. Result: Needs a look.");
  });

  it("degrades without votes: the floor sentence stands alone, no invented judge story", () => {
    const text = caseRead({ floorBlocks: [{ flag: "DISSENT_ERASURE" }], verdict: "BLOCK" });
    expect(text).toBe("The floor didn't hesitate: 1 deterministic fact-check found Dissent erasure, pinned to the transcript. That is why it is flagged.");
    expect(text).not.toMatch(/split|wobbled/);
  });

  it("returns null with nothing to read", () => {
    expect(caseRead({})).toBeNull();
    expect(caseRead({ votes: [] })).toBeNull();
    expect(caseRead()).toBeNull();
  });

  it("never emits an em or en dash", () => {
    const text = caseRead({
      votes: [{ role: "risk_judge", vote: "PASS", confidence: 1.0 }],
      floorBlocks: [{ flag: "DISSENT_ERASURE" }],
      verdict: "BLOCK",
    });
    expect(/[—–]/.test(text)).toBe(false);
  });
});

describe("votesRead — the reviewer-spread read", () => {
  it("mixed uncertain + pass (no block): the judge-noise read", () => {
    const r = votesRead([
      { role: "a", vote: "WARN", confidence: 0.4 },
      { role: "b", vote: "WARN", confidence: 0.5 },
      { role: "c", vote: "PASS", confidence: 1.0 },
    ]);
    expect(r.text).toBe(
      "Two of three reviewers were uncertain, one passed outright. "
      + "This spread is the judge noise, not a verdict: no single reviewer here would have blocked the note.",
    );
    expect(r.confidenceNote).toBe(false);
  });

  it("someone blocked: counts the block, never claims no one would have blocked", () => {
    const r = votesRead([
      { role: "a", vote: "BLOCK", confidence: null },
      { role: "b", vote: "WARN", confidence: 0.5 },
      { role: "c", vote: "PASS", confidence: 1.0 },
    ]);
    expect(r.text).toBe("One of three reviewers voted to block, one was uncertain, one passed outright.");
    expect(r.text).not.toMatch(/would have blocked/);
    expect(r.confidenceNote).toBe(true); // the null confidence -> footnote
  });

  it("all passed / all uncertain branches", () => {
    expect(votesRead([
      { role: "a", vote: "PASS", confidence: 1 }, { role: "b", vote: "PASS", confidence: 1 }, { role: "c", vote: "PASS", confidence: 1 },
    ]).text).toBe("All three reviewers passed it outright.");
    expect(votesRead([
      { role: "a", vote: "WARN", confidence: 0.5 }, { role: "b", vote: "WARN", confidence: 0.4 },
    ]).text).toBe("Both reviewers were uncertain: no single reviewer here would have blocked the note.");
  });

  it("returns null with no votes", () => {
    expect(votesRead([])).toBeNull();
    expect(votesRead(undefined)).toBeNull();
  });
});
