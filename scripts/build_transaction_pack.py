"""Engagement-three oracle: a by-construction PAYMENT-TRANSACTION boundary pack.

The cross-DOMAIN test (not just cross-resource): a non-clinical, non-FHIR JSON artifact.
KB-free by construction — structural conformance is decidable from the artifact + rules
alone, so this needs no domain corpus (the gap the founder flagged). The defect taxonomy +
`_case`/`_recipe` builders are reused verbatim from the FHIR packs; only the clean instances
+ per-field mapping are new (the irreducible domain spec).

Conformance space:
  clean x2                       -> PASS
  ctrl_strip_timestamp           -> PASS  (timestamp optional; FP control)
  struct_strip_id                -> BLOCK (id required)
  struct_strip_amount            -> BLOCK (amount required)
  struct_strip_currency          -> BLOCK (currency required)
  struct_currency_invalid_binding-> BLOCK (currency not ISO-4217 subset)
  struct_status_invalid_binding  -> BLOCK (status not in enum)
  struct_amount_bad_datatype     -> BLOCK (amount not a decimal string -> the NEW datatype class)
  sem_amount_mismatch            -> PASS  (artifact valid; transcript disagrees -> needs source)

Output: data/verification_packs/transaction_v1.jsonl
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "data" / "verification_packs" / "transaction_v1.jsonl"

PACK_ID = "transaction_boundary_v1"
GENERATED_AT = "2026-05-31T00:00:00+00:00"
GENERATOR_VERSION = "lithrim-bench-spike/transaction-boundary-0.1.0"

# two clean, valid payment transactions (hand-authored, by-construction -> true labels).
# amount is a decimal STRING (common in payment APIs) so the datatype check is meaningful.
BASE0 = {
    "id": "txn_8a3f21d0",
    "amount": "120.50",
    "currency": "USD",
    "status": "settled",
    "timestamp": "2026-05-30T09:00:00Z",
    "account": {"reference": "acct_1234"},
}
BASE1 = {
    "id": "txn_5b9e77c4",
    "amount": "1999.00",
    "currency": "EUR",
    "status": "pending",
    "timestamp": "2026-05-28T14:30:00Z",
    "account": {"reference": "acct_5678"},
}


def _short_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def _case(
    *,
    label,
    txn,
    recipe,
    expected_structural_verdict,
    expected_safety_flags,
    transcript="",
    clean=False,
    severity="high",
) -> dict:
    content = json.dumps(txn, sort_keys=True)
    short = _short_hash(
        {"label": label, "artifact_sha": hashlib.sha256(content.encode()).hexdigest()}
    )
    return {
        "case_id": f"bench_{PACK_ID}_{label.lower()}_{short}",
        "pack": PACK_ID,
        "agent_type": "payment_transaction",
        "ground_truth_basis": "constructed",
        "transcript": transcript,
        "artifacts": [
            {"type": "payment_transaction", "content": content, "target_system": "ledger"}
        ],
        "injection_recipes": [recipe] if recipe else [],
        "expected_compliance_verdict": "approve" if clean else ["needs_review", "reject"],
        "expected_artifact_verdict": "PASS" if clean else "BLOCK",
        "expected_structural_verdict": expected_structural_verdict,
        "expected_safety_flags": expected_safety_flags,
        "clean_negative": clean,
        "multi_defect": False,
        "split": "test",
        "severity": severity if not clean else "low",
        "pinned": {
            "generator_version": GENERATOR_VERSION,
            "pack": PACK_ID,
            "deterministic_synthesis": True,
            "validator_profile": "internal://payment-transaction-v1",
        },
        "generated_at": GENERATED_AT,
    }


def _recipe(defect, field, pre, post, flag, note) -> dict:
    return {
        "defect_type": defect,
        "safety_flag": flag,
        "mutated_projection": "artifact.Transaction",
        "mutated_field_or_span": field,
        "pre_value": pre,
        "post_value": post,
        "params": {"note": note},
    }


def main() -> int:
    cases: list[dict] = []
    cases.append(
        _case(
            label="A_CLEAN_0",
            txn=BASE0,
            recipe=None,
            expected_structural_verdict="PASS",
            expected_safety_flags=[],
            clean=True,
        )
    )
    cases.append(
        _case(
            label="A_CLEAN_1",
            txn=BASE1,
            recipe=None,
            expected_structural_verdict="PASS",
            expected_safety_flags=[],
            clean=True,
        )
    )

    p = copy.deepcopy(BASE0)
    pre = p.pop("timestamp", None)
    cases.append(
        _case(
            label="CTRL_STRIP_TIMESTAMP",
            txn=p,
            recipe=_recipe(
                "strip_optional_field",
                "timestamp",
                pre,
                None,
                "NONE",
                "timestamp is optional -> removing it is conformant",
            ),
            expected_structural_verdict="PASS",
            expected_safety_flags=[],
            severity="low",
        )
    )

    for fld in ("id", "amount", "currency"):
        p = copy.deepcopy(BASE0)
        pre = p.pop(fld, None)
        cases.append(
            _case(
                label=f"STRUCT_STRIP_{fld.upper()}",
                txn=p,
                recipe=_recipe(
                    "strip_required_field",
                    fld,
                    pre,
                    None,
                    "STRUCTURAL_MISSING_REQUIRED_FIELD",
                    f"{fld} is required",
                ),
                expected_structural_verdict="BLOCK",
                expected_safety_flags=["STRUCTURAL_MISSING_REQUIRED_FIELD"],
            )
        )

    p = copy.deepcopy(BASE0)
    pre = p.get("currency")
    p["currency"] = "XYZ"
    cases.append(
        _case(
            label="STRUCT_CURRENCY_INVALID_BINDING",
            txn=p,
            recipe=_recipe(
                "invalid_code_binding",
                "currency",
                pre,
                "XYZ",
                "STRUCTURAL_INVALID_CODE",
                "currency must be an ISO-4217 code in {USD|EUR|GBP|JPY|CAD|AUD|CHF|INR}",
            ),
            expected_structural_verdict="BLOCK",
            expected_safety_flags=["STRUCTURAL_INVALID_CODE"],
        )
    )

    p = copy.deepcopy(BASE0)
    pre = p.get("status")
    p["status"] = "bogus"
    cases.append(
        _case(
            label="STRUCT_STATUS_INVALID_BINDING",
            txn=p,
            recipe=_recipe(
                "invalid_code_binding",
                "status",
                pre,
                "bogus",
                "STRUCTURAL_INVALID_CODE",
                "status must be one of pending|settled|failed|refunded",
            ),
            expected_structural_verdict="BLOCK",
            expected_safety_flags=["STRUCTURAL_INVALID_CODE"],
        )
    )

    p = copy.deepcopy(BASE0)
    pre = p.get("amount")
    p["amount"] = "abc"
    cases.append(
        _case(
            label="STRUCT_AMOUNT_BAD_DATATYPE",
            txn=p,
            recipe=_recipe(
                "wrong_datatype",
                "amount",
                pre,
                "abc",
                "STRUCTURAL_INVALID_DATATYPE",
                "amount must be a decimal string (digits with at most one '.')",
            ),
            expected_structural_verdict="BLOCK",
            expected_safety_flags=["STRUCTURAL_INVALID_DATATYPE"],
        )
    )

    semantic_transcript = (
        "Ops: Confirming the wire for two-fifty, $250.00 to the vendor.\nApprover: Yes, 250 even."
    )
    cases.append(
        _case(
            label="SEM_AMOUNT_MISMATCH",
            txn=BASE1,  # artifact unchanged/valid (amount=1999.00)
            recipe=_recipe(
                "value_mismatch_transcript_vs_artifact",
                "amount",
                "artifact=1999.00",
                "transcript=250.00",
                "VALUE_MISMATCH",
                "artifact is structurally valid; conflicts with transcript -> needs source",
            ),
            expected_structural_verdict="PASS",
            expected_safety_flags=["VALUE_MISMATCH"],
            transcript=semantic_transcript,
        )
    )

    OUT.write_text("".join(json.dumps(c, sort_keys=True) + "\n" for c in cases))
    print(f"wrote {len(cases)} cases -> {OUT.name}")
    for c in cases:
        rec = c["injection_recipes"] or [{}]
        d = rec[0].get("defect_type", "clean") if rec and rec[0] else "clean"
        print(f"  {c['expected_structural_verdict']:5s} | {d:42s} | {c['case_id'][-30:]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
