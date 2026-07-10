"""JuteValidatorGenerator — the JUTE validator-authoring loop, ported into the bench
as a DSPy program and scored by the by-construction pack as the acceptance oracle.

This REPLACES the etlp-mapper Copilot's `POST /mappings/generate` loop (whose oracle is
a single (sample_input, expected_output) pair — too weak; it ships confidence:"high"
templates that ERR on 9/10 real cases). Here the generate -> test -> refine loop is OURS
(`forward`), the feedback is the live `:3031 /mappings/test-template`, and the metric is
`bench_accept`: a candidate is trusted ONLY if the multi-case pack accepts it
(clean/control/semantic PASS; every structural defect BLOCKED; 0 FP, 0 ERR).

Determinism: generation/optimization is a one-time AUTHORING step. The accepted template
is captured, content-hash pinned, and (optionally) persisted as an etlp mapping so it can
be applied deterministically via id/title through the wired `StructuralJuteTool`. The bench
— not the LLM's confidence, and not the documented DSL spec (which lies about `replace`) —
decides trust.

`GOLDEN_US_CORE_PATIENT_VALIDATOR` is a hand-verified bench-ACCEPTING validator (live-scored
6/6 defects, 0 FP, 0 ERR). It is the deterministic fallback/pin, a bootstrap demo anchor,
and the offline test fixture, so nothing here requires a live LLM to be reproducible.
"""

from __future__ import annotations

import json
from typing import Any

# The ONLY change from the seeded `fhir-patient-validator` (id 23) is c4 (birthDate):
# seeded c4 = `$if resource.birthDate` (REQUIRED — false-positives on optional-absent AND
# misses present-but-malformed). The fixed c4 is optional + format-checked using ONLY
# runtime-implemented builtins (substr/joinStr/splitStr + lexicographic compare); the
# documented `replace`/`count` are unimplemented and would ERR. (See etlp_client.py.)
GOLDEN_US_CORE_PATIENT_VALIDATOR = r"""$let:
  c1:
    $if: $ resource.identifier
    $then: {name: has-identifier, field: identifier, status: pass, message: Identifier present}
    $else: {name: has-identifier, field: identifier, status: fail, message: Missing identifier}
  c2:
    $if: $ resource.name.0.family && resource.name.0.given
    $then: {name: has-name, field: name, status: pass, message: Name present}
    $else: {name: has-name, field: name, status: fail, message: Missing name with family and given}
  c3:
    $if: $ resource.gender = "male" || resource.gender = "female" || resource.gender = "other" || resource.gender = "unknown"
    $then: {name: valid-gender, field: gender, status: pass, message: Valid gender}
    $else: {name: valid-gender, field: gender, status: fail, message: Invalid or missing gender (must be male|female|other|unknown)}
  c4:
    $if: $ !resource.birthDate || (substr(resource.birthDate,0,1) >= "0" && substr(resource.birthDate,0,1) <= "9" && joinStr("", splitStr(resource.birthDate, "[^0-9-]")) = resource.birthDate)
    $then: {name: valid-birthdate, field: birthDate, status: pass, message: BirthDate absent or a valid FHIR date}
    $else: {name: valid-birthdate, field: birthDate, status: fail, message: birthDate is present but not a valid FHIR date}
  c5:
    $if: $ resource.telecom
    $then: {name: has-telecom, field: telecom, status: pass, message: Telecom present}
    $else: {name: has-telecom, field: telecom, status: fail, message: Missing telecom}
$body:
  $let:
    checks: [$ c1, $ c2, $ c3, $ c4, $ c5]
  $body:
    $let:
      passedChecks:
        $reduce: $ checks
        $as: [acc, c]
        $start: 0
        $body:
          $if: $ c.status = "pass"
          $then: $ acc + 1
          $else: $ acc
    $body:
      request:
        valid: $ passedChecks = 5
        resourceType: Patient
        totalChecks: 5
        passedChecks: $ passedChecks
        failedChecks: $ 5 - passedChecks
        checks: $ checks
"""

# The conformance rules + sample for the FHIR US-Core Patient authoring task.
US_CORE_PATIENT_RULES = (
    "FHIR R4 US-Core Patient conformance validator. Emit ONE check per rule as "
    "{name, field, status: pass|fail, message}; assemble them into "
    "{request: {valid, resourceType, totalChecks, passedChecks, failedChecks, checks: [...]}} "
    "using $let to bind the checks + $reduce to count passes (see the envelope example). Rules:\n"
    "- identifier: REQUIRED (1..*). fail 'Missing identifier' when resource.identifier is absent.\n"
    "- name: REQUIRED (1..*) with family AND given. fail when resource.name.0.family or "
    "resource.name.0.given is absent (this also catches an empty name array []).\n"
    "- gender: REQUIRED (1..1), one of male|female|other|unknown. fail otherwise (this also "
    "catches an absent gender and invalid codes such as 'X').\n"
    "- birthDate: OPTIONAL (0..1). PASS when ABSENT. When PRESENT it must be a FHIR date "
    "(only digits and dashes, starting with a digit: YYYY, YYYY-MM, or YYYY-MM-DD); fail "
    "'birthDate is present but not a valid FHIR date' ONLY when present-and-malformed "
    "(e.g. 'not-a-date'). Do NOT fail merely because birthDate is missing.\n"
    "- telecom: a presence check.\n"
    "Use ONLY runtime-implemented builtins: substr, joinStr, splitStr, toString, and "
    "lexicographic string comparison (>=, <=). Do NOT use replace, count, length, or size."
)


def _defect_type(case: dict) -> str:
    recs = case.get("injection_recipes") or []
    return recs[0].get("defect_type", "clean") if recs and recs[0] else "clean"


def strip_fences(text: str) -> str:
    """Drop a leading ```yaml / ``` fence an LLM may wrap the template in."""
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


# --------------------------------------------------------------------------- #
# the metric (the whole point): score a candidate template against the pack
# --------------------------------------------------------------------------- #
def verdict_for(client: Any, template: str, patient: Any) -> tuple[str, list[str], str | None]:
    """Apply `template` to one resource via test-template -> (PASS|BLOCK|ERR, failed, error)."""
    tt = client.test_template(template, patient)
    if not (isinstance(tt, dict) and tt.get("compiled")):
        return "ERR", [], (tt.get("error") if isinstance(tt, dict) else "no response")
    checks = client.find_checks(tt.get("output"))
    if not checks:
        return "ERR", [], "compiled but produced no checks"
    failed = [c.get("name") for c in checks if str(c.get("status", "")).lower() == "fail"]
    return ("BLOCK" if failed else "PASS"), failed, None


def score_template(client: Any, template: str, cases: list[dict]) -> dict:
    """Score a candidate validator against the by-construction pack.

    A structural validator must: PASS clean negatives, the optional-field control, and the
    semantic case (valid FHIR); BLOCK every structural defect. accepted iff 0 FP, 0 ERR, all
    defects caught. `graded` is the fraction of cases whose verdict matches expectation —
    the gradient the optimizer climbs.
    """
    rows: list[dict] = []
    for case in cases:
        exp = case["expected_structural_verdict"]
        patient = json.loads(case["artifacts"][0]["content"])
        verdict, failed, error = verdict_for(client, template, patient)
        rows.append(
            {
                "exp": exp,
                "verdict": verdict,
                "failed": failed,
                "error": error,
                "defect": _defect_type(case),
                "case_id": case.get("case_id", ""),
            }
        )
    clean = [r for r in rows if r["exp"] == "PASS"]
    defects = [r for r in rows if r["exp"] == "BLOCK"]
    fp = [r for r in clean if r["verdict"] == "BLOCK"]
    err = [r for r in rows if r["verdict"] == "ERR"]
    caught = [r for r in defects if r["verdict"] == "BLOCK"]
    accepted = len(fp) == 0 and len(err) == 0 and len(caught) == len(defects)
    correct = sum(1 for r in rows if r["verdict"] == r["exp"])
    graded = correct / len(rows) if rows else 0.0
    return {
        "accepted": accepted,
        "graded": graded,
        "caught": len(caught),
        "defects": len(defects),
        "fp": len(fp),
        "err": len(err),
        "rows": rows,
    }


def feedback_from(score: dict) -> str:
    """Turn a pack score into refine-loop feedback the generator can act on."""
    parts: list[str] = []
    errs = [r for r in score["rows"] if r["verdict"] == "ERR"]
    if errs:
        sample_err = next((r["error"] for r in errs if r.get("error")), "") or ""
        parts.append(
            f"DID NOT COMPILE for {len(errs)} case(s). Fix THIS exact engine error and return "
            f"a corrected full template: {sample_err[:280]} | Reminders: every $ expression "
            "must be on ONE line (a line break inside $if/$ breaks the YAML parse); never use "
            "replace/count/length/size."
        )
    fps = [r for r in score["rows"] if r["exp"] == "PASS" and r["verdict"] == "BLOCK"]
    if fps:
        parts.append(
            "FALSE POSITIVES — these VALID resources were wrongly BLOCKED (relax the "
            "responsible check): "
            + "; ".join(f"{r['defect']} (failed: {r['failed']})" for r in fps)
        )
    misses = [r for r in score["rows"] if r["exp"] == "BLOCK" and r["verdict"] != "BLOCK"]
    if misses:
        parts.append(
            "MISSED DEFECTS — these must be BLOCKED but PASSED (tighten the responsible "
            "check): " + ", ".join(f"{r['defect']}" for r in misses)
        )
    return " ".join(parts) if parts else "all cases correct"


def make_bench_metric(client: Any, cases: list[dict]):
    """Build a DSPy-style metric(example, pred, trace=None) -> float|bool over the pack.

    With `trace` set (optimizer bootstrap gate) it returns the hard accepted bool — only
    fully bench-accepting templates become few-shot demos. Otherwise it returns the graded
    [0,1] score so the optimizer has a gradient.
    """

    def metric(example: Any, pred: Any, trace: Any = None) -> Any:
        template = strip_fences(getattr(pred, "jute_template", "") or "")
        if not template.strip():
            return False if trace is not None else 0.0
        s = score_template(client, template, cases)
        if trace is not None:
            return bool(s["accepted"])
        return 1.0 if s["accepted"] else s["graded"]

    return metric


# --------------------------------------------------------------------------- #
# DSL grounding
# --------------------------------------------------------------------------- #
_RUNTIME_NOTES = (
    "RUNTIME REALITY (verified against the live engine — TRUST THIS over the spec text):\n"
    "  CRITICAL YAML RULE 1: every `$ ...` expression value MUST be on a SINGLE physical line. "
    "The engine YAML-parses the template first, so a line break inside an $if/$ expression "
    '(e.g. wrapping a long `... || ...` across lines, or a multi-line "(" group) breaks the '
    "parse. Keep each condition on one line, however long.\n"
    "  CRITICAL YAML RULE 2: an expression value MUST start with a literal `$ ` token, e.g. "
    "`$if: $ !resource.birthDate` and `$reduce: $ checks` (NOT `$if: !resource.birthDate`). "
    "A value beginning with `!` without the `$ ` prefix is read as a YAML tag and ERRORS.\n"
    "  WORKS: $let, $reduce ($as [acc,c] $start N $body), $if/$then/$else, paths "
    "(resource.a.0.b), && || ! , = != >= <= (strings compare lexicographically), "
    "substr(s,start,end), joinStr(sep,array), splitStr(s,regex), toString(x).\n"
    "  DOES NOT WORK (raises 'call nil or non-function' at apply time — NEVER use): "
    "replace, count, length, size.\n"
    "  Idiom 'string s contains ONLY characters from an allowed set': "
    'joinStr("", splitStr(s, "[^<allowed>]")) = s  (fill <allowed> with a regex class).\n'
    '  Idiom \'first char is a digit\': substr(s,0,1) >= "0" && substr(s,0,1) <= "9" '
    "(strings compare lexicographically).\n"
    "  Optional field: guard with !resource.field || (<checks that run only when present>)."
)

# Shows ONLY the assembly shape ($let + $reduce + the {name,field,status,message} check
# dict) with a generic placeholder check — NOT the answer. The generator must author the
# discriminating checks (esp. the optional+format-checked birthDate) from the rules + the
# pack feedback, which is the whole point.
_ENVELOPE_SKELETON = r"""# OUTPUT SHAPE ONLY — author your OWN checks c1..cN from the rules; do NOT copy this check:
$let:
  c1:
    $if: $ resource.someField
    $then: {name: example-check, field: someField, status: pass, message: present}
    $else: {name: example-check, field: someField, status: fail, message: missing}
  # ... define the remaining checks the rules require, each as $if/$then/$else ...
$body:
  $let:
    checks: [$ c1]    # list EVERY check here
  $body:
    $let:
      passedChecks:
        $reduce: $ checks
        $as: [acc, c]
        $start: 0
        $body:
          $if: $ c.status = "pass"
          $then: $ acc + 1
          $else: $ acc
    $body:
      request:
        valid: $ passedChecks = 1
        resourceType: Patient
        totalChecks: 1
        passedChecks: $ passedChecks
        failedChecks: $ 1 - passedChecks
        checks: $ checks
"""


# EXTRACTOR-ONLY grounding addendum (NARR-7 / G1). This is appended ONLY on the
# `jute_extractor` path (`for_extractor=True`) — the VALIDATOR path (`jute_dspy`) NEVER sees it,
# so its excerpt stays byte-identical (R1: _RUNTIME_NOTES is SHARED). These facts are EMPIRICALLY
# DERIVED from the live :3031 spike (NOTE_jute_extractor_wired_demo_2026-06-17.md §A): they are
# the exact quirks that took a blind first-shot on a NEW join-heavy shape (GitHub issues⋈comments)
# to 0/3, and a one-refine round to 3/3. The validator authors single-resource CHECKS; the
# extractor must author a relational JOIN across collections — a different burden that needs the
# join idiom + the two traps + the deployed string/concat quirks.
_EXTRACTOR_NOTES = (
    "EXTRACTOR — AUTHORING A RELATIONAL JOIN (TRUST THIS over the spec; verified live on the "
    "deployed engine — the deployed build differs from the documented spec):\n"
    "  FEED-SHAPE: the engine wraps your input as {resource: <input>}, so address the dump as "
    "`resource.<topKey>` (e.g. resource.comments, resource.issues).\n"
    "  ITERATE one record per entry of the SOURCE collection with `$map: $ resource.<coll>` "
    "`$as: e` `$body: ...` — the output row-count equals the iterated collection's length.\n"
    "  JOIN-BY-KEY (the ROBUST idiom): to attach a related collection's row, find it by key with "
    "a nested `$reduce` (find-by-key): `$reduce: $ resource.<other>` `$as: [acc, x]` "
    "`$start: null` `$body: { $if: $ x.key = e.joinKey, $then: $ x, $else: $ acc }`. The "
    "$reduce/$let/$map each bind their var INTO the existing scope, so the inner $body CAN read "
    "the outer loop var.\n"
    "  STRING LITERALS: DOUBLE QUOTES ONLY — `\"github\"`, NOT `'github'`. Single-quote literals "
    "FAIL TO PARSE on the deployed engine (the served spec lies). This was the dominant first-"
    "shot failure on a new shape.\n"
    "  CONCAT with the `+` operator: `\"gh-\" + toString(x.id)`. joinStr is (sep, ARRAY) — NOT a "
    "variadic concat; do NOT use joinStr to glue scalars.\n"
    "  A $body/$reduce/$let value that SELECTS between values MUST be a STRUCTURED $if OBJECT "
    "`{ $if: $ cond, $then: $ a, $else: $ b }` — NEVER an inline string `\"$ $if: ...\"`.\n"
    "  WORKS: len(coll) (= the count; 'count'/'length'/'size' are ABSENT), groupBy(keyfn, coll) "
    "(a clean keyed index).\n"
    "  JOIN TRAP 1 (predicate `.0`): `coll.*(this.k = key).0.field` does NOT take the first match "
    "— after a predicate, `.0` maps INTO each match and collapses to `[]` → the joined field is "
    "null (a MIS-JOIN). Use the $reduce find-by-key idiom instead.\n"
    "  JOIN TRAP 2 (assoc index): an `assoc`-built index then `.(key)` returns null — assoc makes "
    "STRING keys but a dynamic `.(...)` looks up a KEYWORD (string-vs-keyword mismatch).\n"
    "  NO `#` in a YAML scalar (it starts a comment and truncates the expression)."
)


def render_dsl_excerpt(
    spec: dict, *, include_envelope_example: bool = True, for_extractor: bool = False
) -> str:
    """Render a compact, TRUTHFUL grounding excerpt from the live DSL spec.

    The served spec documents builtins the runtime lacks, so the rendered operators/builtins
    are followed by the verified runtime notes + the output-envelope example.

    `for_extractor=True` (NARR-7) appends the EXTRACTOR-ONLY relational-JOIN grounding addendum
    (`_EXTRACTOR_NOTES`) — the join idiom, the two join traps, the deployed string/concat quirks.
    It is STRICTLY ADDITIVE: the default (validator) excerpt is byte-identical with/without the
    flag absent, so `jute_dspy`'s SHARED `_RUNTIME_NOTES` is never regressed (R1).
    """
    chunks: list[str] = []
    if isinstance(spec, dict) and spec:
        directives = spec.get("directives")
        if directives:
            chunks.append("DIRECTIVES:\n" + json.dumps(directives, indent=1)[:1400])
        ops = spec.get("operators", {})
        if ops:
            chunks.append(
                "OPERATORS (precedence):\n" + json.dumps(ops.get("precedence_order", []), indent=1)
            )
    chunks.append(_RUNTIME_NOTES)
    if include_envelope_example:
        chunks.append(
            "OUTPUT ENVELOPE — your template MUST produce checks as a list of "
            "{name, field, status, message}. Follow this assembly shape (author your own "
            "checks):\n" + _ENVELOPE_SKELETON
        )
    if for_extractor:
        chunks.append(_EXTRACTOR_NOTES)
    return "\n\n".join(chunks)


# --------------------------------------------------------------------------- #
# the DSPy program: refine loop owned by the bench
# --------------------------------------------------------------------------- #
def _build_signature():
    import dspy

    class JuteValidatorSignature(dspy.Signature):
        """Author a JUTE conformance validator (raw YAML) for a FHIR resource.

        Ground STRICTLY in the DSL excerpt's RUNTIME REALITY notes — some documented
        builtins are unimplemented and will fail. The template must emit a list of
        {name, field, status: pass|fail, message} checks inside the request envelope.
        If prior_error is non-empty, FIX exactly what it reports and return a corrected
        full template. Output raw YAML only — no markdown fences, no commentary.
        """

        dsl_excerpt: str = dspy.InputField(desc="the working subset of the JUTE DSL + idioms")
        conformance_rules: str = dspy.InputField(desc="the per-field rules to enforce")
        sample_input: str = dspy.InputField(desc="a clean example resource (JSON)")
        prior_template: str = dspy.InputField(desc="the previous attempt, or '' on the first try")
        prior_error: str = dspy.InputField(
            desc="compile/score feedback on the prior attempt, or ''"
        )
        jute_template: str = dspy.OutputField(desc="the JUTE validator as raw YAML")

    return JuteValidatorSignature


def build_generator(
    client: Any,
    dsl_excerpt: str,
    cases: list[dict],
    *,
    max_iters: int = 3,
    predictor: Any = None,
    seed_template: str = "",
    seed_feedback: str = "",
):
    """Construct a JuteValidatorGenerator. `predictor` is injectable for offline tests
    (a callable returning an object with `.jute_template`); defaults to a live
    dspy.ChainOfThought over the signature.

    `seed_template` + `seed_feedback` seed iteration 0 with a KNOWN-GOOD validator and a
    targeted instruction — so the loop makes a MINIMAL edit (e.g. close a mutation survivor)
    instead of re-deriving from scratch. This is what makes incremental hardening converge
    (gating on a large expanded oracle from a blank start does NOT — it overwhelms the model)."""
    import dspy

    class JuteValidatorGenerator(dspy.Module):
        def __init__(self) -> None:
            super().__init__()
            self.gen = (
                predictor if predictor is not None else dspy.ChainOfThought(_build_signature())
            )
            self.client = client
            self.dsl_excerpt = dsl_excerpt
            self.cases = cases
            self.max_iters = max_iters
            self.seed_template = seed_template
            self.seed_feedback = seed_feedback

        def forward(self, conformance_rules: str, sample_input: Any) -> Any:
            sample = json.loads(sample_input) if isinstance(sample_input, str) else sample_input
            sample_json = json.dumps(sample)
            prior_template, prior_error = self.seed_template, self.seed_feedback
            history: list[dict] = []
            best: str | None = None
            best_score: dict | None = None
            for it in range(self.max_iters):
                pred = self.gen(
                    dsl_excerpt=self.dsl_excerpt,
                    conformance_rules=conformance_rules,
                    sample_input=sample_json,
                    prior_template=prior_template,
                    prior_error=prior_error,
                )
                template = strip_fences(getattr(pred, "jute_template", "") or "")
                s = (
                    score_template(self.client, template, self.cases)
                    if template.strip()
                    else {
                        "accepted": False,
                        "graded": 0.0,
                        "caught": 0,
                        "defects": 0,
                        "fp": 0,
                        "err": 0,
                        "rows": [],
                    }
                )
                history.append(
                    {
                        "iter": it,
                        "accepted": s["accepted"],
                        "graded": round(s["graded"], 3),
                        "caught": s["caught"],
                        "fp": s["fp"],
                        "err": s["err"],
                    }
                )
                if best_score is None or s["graded"] > best_score["graded"]:
                    best, best_score = template, s
                if s["accepted"]:
                    break
                prior_template = template
                prior_error = feedback_from(s)
            return dspy.Prediction(
                jute_template=best or "",
                accepted=bool(best_score and best_score["accepted"]),
                score=best_score,
                history=history,
            )

    return JuteValidatorGenerator()


def best_of_n(make_gen, conformance_rules: str, sample_input: Any, *, n: int = 3) -> Any:
    """Run the refine-loop generator up to N independent times; return the first
    bench-accepted prediction, else the highest-graded one. `make_gen` is a 0-arg
    factory so each attempt is a fresh module instance."""
    best = None
    for _ in range(n):
        pred = make_gen().forward(conformance_rules=conformance_rules, sample_input=sample_input)
        if getattr(pred, "accepted", False):
            return pred
        graded = (getattr(pred, "score", None) or {}).get("graded", 0.0)
        if best is None or graded > (getattr(best, "score", None) or {}).get("graded", 0.0):
            best = pred
    return best
