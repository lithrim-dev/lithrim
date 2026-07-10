---
name: lithrim-snomed-setup
description: Wire a local Hermes SNOMED CT terminology server into Lithrim's grounding floor. Licensing gate first; the user must obtain the SNOMED release themselves, then this skill builds the index, mounts it, authors the tool, and verifies one subsumption lookup.
---

# Set up the SNOMED terminology floor (Hermes)

The full guide is `docs/SNOMED_SETUP.md` in the repo; this is the agent-runnable path.
This component is optional: Lithrim grades without it (terminology checks resolve to
inconclusive); it is required for code-grounded floor checks.

## 0. THE LICENSING GATE (stop here first)

**SNOMED CT releases are licensed content.** You must NOT download, fetch, or automate
the acquisition of any SNOMED CT release. Stop and tell the user:

> SNOMED CT requires a license. Obtain a release you are entitled to use yourself:
> via SNOMED International MLDS (most countries), UMLS/NLM (United States), or NHS
> TRUD (United Kingdom). Tell me the path to the downloaded release folder when you
> have it.

Do not proceed past this point until the user confirms they have a licensed release on
disk and gives you its path. Hermes itself (the software) is open source and fine to
download; the terminology data is not yours to fetch.

## 1. Get Hermes (the open-source jar)

Download the latest `hermes.jar` from https://github.com/wardle/hermes/releases/latest
(the jar asset). Verify a modern Java is available for the host-side index build:

```bash
java -version   # 17+ required; 21 recommended (matches the Lithrim container JRE)
```

Failure handling: no Java, or too old: ask the user to install a JDK/JRE 21 (never
attempt a system-level install yourself without asking).

## 2. Build the index from the user's release

With the user-provided release path:

```bash
java -jar hermes.jar --db snomed.db import <user-release-path>/ index compact
```

Verify: the command exits 0 and a `snomed.db` now exists. This takes a few minutes.

## 3. Mount it into the stack

Place the files in the `snomed/` directory next to the compose file the user launched
(the repo checkout's `snomed/` dir, or a created one beside the standalone deploy
compose file):

```
snomed/
  hermes.jar
  snomed.db
  logback-stderr.xml   # tracked in the repo as snomed/logback-stderr.xml; copy it in on the no-clone path
```

Then restart the stack: `docker compose up -d`. Verify the mount from inside:

```bash
docker compose exec bff ls /snomed
```

Expect the jar, the db, and `logback-stderr.xml`. Failure handling: an empty listing
means the files are not next to the compose file that was launched; fix and restart.

## 4. Author the terminology tool (container paths)

Register the tool against the BFF. The args MUST use container paths (`/snomed/...`)
and MUST lead with the logback flag (without it, Hermes logs to stdout and corrupts the
MCP JSON stream):

```bash
curl -s -X POST http://localhost:8787/v1/tools -H 'Content-Type: application/json' \
  -d '{"manifest": {"id": "hermes_snomed", "kind": "tool", "transport": "service", "implements": "tool.terminology", "service": {"mcp": {"command": "java", "args": ["-Dlogback.configurationFile=/snomed/logback-stderr.xml", "-jar", "/snomed/hermes.jar", "--db", "/snomed/snomed.db", "mcp"]}}}}'
```

Expect `{"status": "ok", "tool_id": "hermes_snomed", ...}`.

## 5. Verify with one subsumption lookup

Health-check (spawns the jar in-container, lists its MCP tools):

```bash
curl -s -X POST http://localhost:8787/v1/tools/test -H 'Content-Type: application/json' \
  -d '{"manifest": {"id": "hermes_snomed", "kind": "tool", "transport": "service", "implements": "tool.terminology", "service": {"mcp": {"command": "java", "args": ["-Dlogback.configurationFile=/snomed/logback-stderr.xml", "-jar", "/snomed/hermes.jar", "--db", "/snomed/snomed.db", "mcp"]}}}}'
```

Expect `"ok": true` with a list of tool names. Then one real lookup (myocardial
infarction 22298006 is-a disease 64572001):

```bash
docker compose exec bff python -c "
from lithrim_bench.verification.mcp_client import McpStdioClient
args = ['-Dlogback.configurationFile=/snomed/logback-stderr.xml',
        '-jar', '/snomed/hermes.jar', '--db', '/snomed/snomed.db', 'mcp']
with McpStdioClient(command='java', args=args) as c:
    print(c.call_tool('subsumed_by', {'concept_id': 22298006, 'subsumer_id': 64572001}))
"
```

Expect a `subsumedBy` true result. Failure handling: JSON parse errors mean the logback
flag is missing or misplaced (it must precede `-jar`); a file-not-found means the step-3
mount is wrong; see the troubleshooting table in `docs/SNOMED_SETUP.md`.
