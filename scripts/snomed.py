"""Ask the live SNOMED server one question, both directions.

  docker exec -i lithrim-repro-bff-1 python3 - < snomed.py                  # JME vs Epilepsy
  docker exec -i lithrim-repro-bff-1 python3 - 34000006 24526004 < snomed.py  # Crohn's vs IBD
"""
import sys

from lithrim_bench.verification.mcp_client import McpStdioClient

args = [a for a in sys.argv[1:] if a.isdigit()]
CHILD, PARENT = (int(args[0]), int(args[1])) if len(args) >= 2 else (6204001, 84757009)

with McpStdioClient(
    command="java",
    args=["-Dlogback.configurationFile=/snomed/logback-stderr.xml",
          "-jar", "/snomed/hermes.jar", "--db", "/snomed/snomed.db", "mcp"],
) as c:
    names = {d["conceptId"]: d["term"] for d in c.call_tool(
        "fully_specified_name", {"concept_id": [CHILD, PARENT]})}
    fwd = c.call_tool("subsumed_by", {"concept_id": CHILD, "subsumer_id": PARENT})
    rev = c.call_tool("subsumed_by", {"concept_id": PARENT, "subsumer_id": CHILD})

print()
print(f"  {CHILD}  {names.get(CHILD, '?')}")
print(f"  {PARENT}  {names.get(PARENT, '?')}")
print()
print(f"  is {CHILD} a kind of {PARENT} ?   ->  {str(fwd.get('subsumedBy')).upper()}")
print(f"  is {PARENT} a kind of {CHILD} ?   ->  {str(rev.get('subsumedBy')).upper()}")
print()
verdict = ("STRICT DESCENDANT: the note is more specific than the record. UPCODE."
           if fwd.get("subsumedBy") and not rev.get("subsumedBy")
           else "not a strict descendant: no upcode on this pair")
print(f"  {verdict}")
print()
