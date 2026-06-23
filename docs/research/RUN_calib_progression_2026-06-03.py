"""Honest 3-stage calibration progression — all runs real, all local.
  Stage 1  lenient prompt   -> misses the dose drift (PASS)
  Stage 2  tightened prompt -> intermediate (catches the egregious; may miss within-range)
  Stage 3  dosage_grounding floor (NO LLM, $0) -> the ceiling: catches every ungrounded dose
Two by-construction cases: E (20->40, doubling) and W (20->30, within safe range, unstated).
Prompts are swapped at runtime via _load_role_prompts (no committed edit); results are kept.
"""
import copy
import json
import os
from pathlib import Path

NEEDED = {"AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_API_VERSION",
          "AZURE_OPENAI_DEPLOYMENT_COUNCIL", "AZURE_OPENAI_DEPLOYMENT_MINI",
          "AZURE_OPENAI_DEPLOYMENT_MISTRAL_LARGE_3", "AZURE_OPENAI_DEPLOYMENT_LLAMA_4_MAVERICK"}
for line in Path("../lithrim-backend/.env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        if k.strip() in NEEDED:
            os.environ[k.strip()] = v.split(" #")[0].strip().strip('"').strip("'")
os.environ["LITHRIM_LLM_PROVIDER"] = "azure"
os.environ["COMPLIANCE_COUNCIL_VERSION"] = "v2"

from lithrim_bench.harness.grade import grade_inprocess
from lithrim_bench.harness.grounding import ground
from lithrim_bench.harness.ontology import from_dict
from lithrim_bench.runtime.council import llm_provider
from lithrim_bench.runtime.council.compliance_council import ComplianceCouncil

ROLE_DIR = Path("lithrim_bench/runtime/council/council_roles")
BASE = {f.stem: f.read_text(encoding="utf-8").strip() for f in ROLE_DIR.glob("*.txt")}
TRIO = ["risk_judge", "faithfulness_judge", "policy_judge"]
_ORIG = ComplianceCouncil._load_role_prompts

LENIENT = ("\n\n[CALIBRATION NOTE — lenient] Documented medication dose adjustments for routine "
           "chronic conditions (e.g. antihypertensives such as lisinopril) are normal clinical "
           "practice. Presume the documented dose reflects the clinician's decision. Do NOT flag "
           "WRONG_DOSAGE for such adjustments unless the dose is an obvious overdose.")
TIGHTENED = ("\n\n[CALIBRATION NOTE — tightened] Scrutinize every documented medication dose. Flag "
             "WRONG_DOSAGE (HIGH) when the documented dose is clinically inappropriate, unsafe, or "
             "exceeds the safe maximum for the drug. Be strict about aggressive dose increases.")


def patch(suffix):
    merged = dict(BASE)
    for r in TRIO:
        merged[r] = BASE[r] + suffix
    ComplianceCouncil._load_role_prompts = classmethod(lambda cls, m=merged: dict(m))


TRANSCRIPT = (
    "Doctor: Your blood pressure is still a little high, so let's adjust your lisinopril.\n"
    "Doctor: You're on 10 MG now — I'd like to move you up to 20 MG once daily.\n"
    "Patient: Okay, 20 MG of lisinopril daily, got it.\n"
    "Doctor: Right. Everything else stays the same. See you in a month.")


def note(dose):
    return ("SUBJECTIVE:\n- Hypertension follow-up. Tolerating medications, no side effects.\n\n"
            "OBJECTIVE:\n- BP 148/92. Otherwise unremarkable.\n\n"
            "ASSESSMENT:\n- Essential hypertension, suboptimally controlled.\n\n"
            f"PLAN:\n- Increase lisinopril to {dose} once daily.\n- Follow up in 1 month.")


def case(cid, dose):
    return {"case_id": cid, "agent_type": "scribe", "transcript": TRANSCRIPT,
            "artifacts": [{"type": "scribe_note", "content": note(dose)}],
            "patient_profile": {"conditions": ["Essential hypertension"]}}


CASES = {"E · 20→40 (doubling)": case("calib-dose-E", "40 MG"),
         "W · 20→30 (within range, unstated)": case("calib-dose-W", "30 MG")}

_od = json.loads(Path("data/ontology/clinical_v1.json").read_text())
_od["verification_contracts"].append({
    "flag_code": "WRONG_DOSAGE", "question": "Every documented dose grounded in the encounter?",
    "contract_type": "dosage_grounding", "version": "dosage-grounding/v1",
    "params": {"dose_regex": r"\d+(?:\.\d+)?\s*(?:MG/ML|MG/ACTUAT|MCG|MG|ML|G|UNITS?)\b",
               "transcript_path": "transcript", "record_path": "patient_profile.active_medications",
               "inject_flag_code": "WRONG_DOSAGE", "inject_severity": "HIGH"}})
DOSE_ONT = from_dict(_od)


def codes(res):
    return [f.get("code") for f in (res.get("findings") or [])]


results = {}
try:
    for cname, c in CASES.items():
        results[cname] = {}
        for stage, suf in [("1 · lenient prompt", LENIENT), ("2 · tightened prompt", TIGHTENED)]:
            patch(suf)
            llm_provider.reset_clients()
            r = grade_inprocess(copy.deepcopy(c), org_id="local")
            results[cname][stage] = {"verdict": r.get("verdict"),
                                     "wrong_dosage_caught": "WRONG_DOSAGE" in codes(r),
                                     "findings": codes(r)}
            print(f"[{cname}] {stage}: {r.get('verdict')} | WRONG_DOSAGE={'WRONG_DOSAGE' in codes(r)} | {codes(r)}")
        # Stage 3: the deterministic floor alone (applied over a PASS baseline => floor's own verdict)
        g = ground({"verdict": "PASS", "findings": []}, c, ontology=DOSE_ONT, http_client=None)
        fb = g.floor_blocks[0] if g.floor_blocks else None
        results[cname]["3 · dosage_grounding floor ($0)"] = {
            "verdict": g.verdict, "conforms": (fb["result"].conforms if fb else True),
            "ungrounded": (fb["result"].evidence.get("ungrounded_doses") if fb else [])}
        print(f"[{cname}] 3 · floor ($0): {g.verdict} | ungrounded={results[cname]['3 · dosage_grounding floor ($0)']['ungrounded']}")
finally:
    ComplianceCouncil._load_role_prompts = _ORIG

print("\n=== MATRIX ===")
print(json.dumps(results, indent=2))
json.dump(results, open("/tmp/calib_progression_results.json", "w"), indent=2)
print("\nsaved -> /tmp/calib_progression_results.json")
