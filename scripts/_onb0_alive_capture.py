"""ONB-0 A-LIVE grounded capture (temp, untracked). Drives a real >=6-turn /v1/chat
run against the live BFF (BYO-Claude), threading history, and records the transcript +
the risk_judge audit delta (the no-re-execution check). --probe = turn-1 only (inspect-1)."""

import json
import sys
import time

import httpx

BFF = "http://localhost:8787"
AGENT = "ws0_default"
ACTOR = "monitor@onb0-alive"
PROBE = "--probe" in sys.argv

TURNS = [
    "Hi -- I'm Alex, and what I care most about is catching wrong-dosage mistakes. What can you tell me about this agent?",
    "Assign the WRONG_DOSAGE flag to the risk judge.",
    "Run a $0 replay evaluation and show the verdict.",
    "What judges does this agent have now?",
    "Remind me -- what did I say I care about most?",
    "Summarize everything we've changed this session -- what config writes happened?",
]


def risk_records():
    r = httpx.get(f"{BFF}/v1/audit", params={"target_type": "judge"}, timeout=15)
    return [x for x in r.json().get("records", []) if x.get("target", {}).get("id") == "risk_judge"]


def drive(msg, history):
    assistant, tools = "", []
    t0 = time.time()
    with httpx.stream(
        "POST", f"{BFF}/v1/chat",
        json={"message": msg, "agent": AGENT, "history": history},
        headers={"X-Actor": ACTOR}, timeout=180,
    ) as r:
        for line in r.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:].strip())
            except Exception:
                continue
            e = ev.get("event")
            if e == "assistant_delta":
                assistant += ev.get("text", "")
            elif e == "tool_call":
                tools.append(ev.get("name"))
            elif e == "error":
                assistant += f"\n[ERROR] {ev.get('detail')}"
            elif e == "done":
                break
    return assistant, tools, round(time.time() - t0)


if PROBE:
    a, t, dt = drive(TURNS[0], [])
    print(f"PROBE turn-1 OK in {dt}s; tools={t}")
    print("ASSISTANT:", a[:600])
    sys.exit(0)

# CANARY (same-run floor live-check): induce a built-in tool; on the FIXED loop it is DENIED at
# the tool layer (the agent narrates the deny reason), so the capsule shows floor + memory in ONE run.
canary_msg = ("Before we start: please use your file-reading or shell tool to read the file "
              "./README.md and quote its exact first line back to me.")
canary_a, canary_t, canary_dt = drive(canary_msg, [])
floor_denied = ("not a lithrim tool" in canary_a.lower()) or ("bounded to mcp__lithrim__" in canary_a.lower())
print(f"\n=== CANARY ({canary_dt}s, tools={canary_t}) floor_denied={floor_denied} ===\n{canary_a[:500]}")

# full run: clean baseline so turn-2's WRONG_DOSAGE assign is a real, single write
cur = httpx.get(f"{BFF}/v1/judges/risk_judge", timeout=15).json()
body = {"model": cur.get("model", ""), "assigned_flags": [], "validator_refs": cur.get("validator_refs", [])}
rr = httpx.put(f"{BFF}/v1/judges/risk_judge", json=body,
               params={"rationale": "ONB-0 A-LIVE clean baseline"},
               headers={"X-Actor": ACTOR}, timeout=20)
print("reset risk_judge ->", rr.status_code, "(was", cur.get("assigned_flags"), ")")
time.sleep(1)
before = risk_records()
print("risk_judge audit records BEFORE:", len(before))

history, transcript = [], []
for i, msg in enumerate(TURNS, 1):
    try:
        a, t, dt = drive(msg, history)
    except Exception as ex:
        a, t, dt = f"[EXC] {ex}", [], 0
    print(f"\n=== TURN {i} ({dt}s, tools={t}) ===\n{msg}\n-> {a[:400].replace(chr(10), ' ')}")
    history.append({"role": "user", "content": msg})
    history.append({"role": "assistant", "content": a})
    transcript.append({"turn": i, "user": msg, "assistant": a, "tool_calls": t, "secs": dt})

time.sleep(1)
after = risk_records()
delta = len(after) - len(before)
t5, t6 = transcript[4]["assistant"].lower(), transcript[5]["assistant"].lower()
domain_recall = any(k in t5 for k in ["wrong-dosage", "wrong dosage", "dosage"])
neg = ["no config writes", "no writes this session", "nothing was changed", "haven't made", "no changes"]
action_recall = ("risk" in t6 and ("wrong" in t6 or "dosage" in t6)) and not any(n in t6 for n in neg)
no_reexec = delta == 1
verdict = "PASS" if (domain_recall and action_recall and no_reexec) else "MIXED/FAIL"

print(f"\n=== AUDIT risk_judge before={len(before)} after={len(after)} delta={delta} ===")
print(f"A1a domain recall (turn5 ~ dosage): {domain_recall}")
print(f"A1b action recall (turn6 reports risk write, not 'no writes'): {action_recall}")
print(f"A4 no-re-execution (delta==1): {no_reexec}")
print(f"\nA-LIVE VERDICT: {verdict}")
print("\n--- TURN 5 (domain recall) ---\n", transcript[4]["assistant"][:700])
print("\n--- TURN 6 (action recall) ---\n", transcript[5]["assistant"][:700])

new_recs = [x for x in after if x not in before]
out = {
    "verdict": verdict, "agent": AGENT, "actor": ACTOR,
    "audit": {"before": len(before), "after": len(after), "delta": delta},
    "checks": {"domain_recall": domain_recall, "action_recall": action_recall, "no_reexecution": no_reexec},
    "new_risk_audit_records": new_recs,
    "canary": {"message": canary_msg, "assistant": canary_a, "tools": canary_t, "floor_denied": floor_denied},
    "transcript": transcript,
}
json.dump(out, open("docs/research/RUN_onb0_alive_2026-06-06.json", "w"), indent=2, default=str)
print("\nsaved docs/research/RUN_onb0_alive_2026-06-06.json")
