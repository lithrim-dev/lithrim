# SNOMED terminology setup (Hermes)

Wire a local [Hermes](https://github.com/wardle/hermes) SNOMED CT terminology server into
Lithrim's grounding floor. This is a **data-preparation guide, not a new service**: the
Docker stack already ships everything needed to run Hermes in-container (a JRE 21 in the
BFF image, the read-only `./snomed` mount, the stdio MCP client). You supply the two
things this repo cannot: the Hermes jar and a SNOMED CT release you are licensed to use.

**Honest scope note: this is an optional component.** The core grades fine without it;
connectors resolve to *inconclusive* when absent, never a crash and never a silent
verdict flip. What needs it: the terminology floor checks (code-grounded subsumption,
e.g. the `terminology_subsumption` contract) that let the deterministic floor confirm or
override a judge on coded concepts.

Commands below were verified against the `wardle/hermes` README (`main` branch, fetched
2026-07-10) and its MCP documentation (`doc/mcp.md`, same fetch).

## 1. Licensing reality, first

**SNOMED CT releases are licensed content and are NEVER redistributed by this repo** or
baked into any published image. Before anything else, obtain a release you are entitled
to use:

- **Most countries:** register with your national release centre through
  [SNOMED International MLDS](https://mlds.ihtsdotools.org). Member-state releases are
  free to residents of member territories; affiliate licenses cover others.
- **United States:** SNOMED CT US Edition ships through the
  [UMLS](https://www.nlm.nih.gov/research/umls/index.html) (a free UMLS Metathesaurus
  license from the NLM).
- **United Kingdom:** [NHS TRUD](https://isd.digital.nhs.uk).

Download the release yourself with your own credentials. Nothing in this guide (or in
any Lithrim tooling) fetches SNOMED content for you.

## 2. Get Hermes

Hermes itself is open source (EPL-2.0). Download `hermes.jar` from the
[wardle/hermes releases page](https://github.com/wardle/hermes/releases/latest).

You need a JDK/JRE to run it on the host while building the index; the Hermes README
says Java 17+, and recent uberjars are built on JDK 21, which is what the Lithrim BFF
container ships. If a host-side run fails with an `UnsupportedClassVersionError`, your
host Java is too old; use 21.

## 3. Build the index/db locally

From the directory holding your licensed release (per the Hermes README; `hermes` in its
docs means `java -jar hermes.jar` when you use the jar):

```bash
java -jar hermes.jar --db snomed.db import <path-to-your-snomed-release>/ index compact
```

If your distributor supports automated download with your own API key (UK TRUD, or an
MLDS member nation), the Hermes README's one-shot equivalent is:

```bash
java -jar hermes.jar --progress --db snomed.db install --dist uk.nhs/sct-monolith --api-key trud-api-key.txt --cache-dir /tmp/trud index compact
```

Import and indexing take a few minutes; the result is a self-contained `snomed.db`
(no external services).

## 4. Drop both into `./snomed/`

The repo's `./snomed/` directory (empty and gitignored by design, see
`snomed/README.md`) is bind-mounted read-only into the BFF container at `/snomed`:

```
snomed/
  hermes.jar
  snomed.db              # the index you just built (file or directory)
  logback-stderr.xml     # already tracked in this repo
```

Using the no-clone `deploy/docker-compose.yml` stack? Create `snomed/` next to the
compose file; the mount is identical. Restart the stack (`docker compose up`) so the
mount picks the files up.

## 5. The logback-stderr fix (required for MCP)

Hermes' default logging writes timestamped lines to **stdout**, which corrupts the MCP
stdio JSON-RPC stream (the client dies with errors like `Extra data: line 1 column 5`).
The tracked `snomed/logback-stderr.xml` routes logs to stderr instead. Always pass:

```
-Dlogback.configurationFile=/snomed/logback-stderr.xml
```

as the first argument when spawning Hermes as an MCP server, as in the tool wiring below.

## 6. Author the terminology tool (container paths)

The MCP server is spawned **inside** the BFF container by the stdio MCP client, so the
tool must be declared with **container** paths (`/snomed/...`), never host paths. Author
it in the UI ToolBuilder, or `POST /v1/tools` with a `kind: tool` manifest (the contract
is `docs/specs/SPEC_TOOL_CONNECTORS.md`; manifests carry config only, never secrets):

```json
{
  "manifest": {
    "id": "hermes_snomed",
    "kind": "tool",
    "transport": "service",
    "implements": "tool.terminology",
    "service": {
      "mcp": {
        "command": "java",
        "args": [
          "-Dlogback.configurationFile=/snomed/logback-stderr.xml",
          "-jar", "/snomed/hermes.jar",
          "--db", "/snomed/snomed.db",
          "mcp"
        ]
      }
    }
  }
}
```

A flag's verification contract can then name this tool (for example the core
`terminology_subsumption` contract with `params.tool = "hermes_snomed"`), and the floor
grounds coded concepts by is-a subsumption instead of string match.

## 7. Verify with one subsumption lookup

First, the built-in health check spawns the jar in-container and lists its tools:

```bash
curl -s -X POST http://localhost:8787/v1/tools/test -H 'Content-Type: application/json' \
  -d '{"manifest": {"id": "hermes_snomed", "kind": "tool", "transport": "service", "implements": "tool.terminology", "service": {"mcp": {"command": "java", "args": ["-Dlogback.configurationFile=/snomed/logback-stderr.xml", "-jar", "/snomed/hermes.jar", "--db", "/snomed/snomed.db", "mcp"]}}}}'
```

Expect `{"ok": true, "tools": [...]}` with dozens of tool names. Then one real lookup:
myocardial infarction (`22298006`) is-a disease (`64572001`) must ground true:

```bash
docker compose exec bff python -c "
from lithrim_bench.verification.mcp_client import McpStdioClient
args = ['-Dlogback.configurationFile=/snomed/logback-stderr.xml',
        '-jar', '/snomed/hermes.jar', '--db', '/snomed/snomed.db', 'mcp']
with McpStdioClient(command='java', args=args) as c:
    print(c.call_tool('subsumed_by', {'concept_id': 22298006, 'subsumer_id': 64572001}))
"
```

Expect a result whose `subsumedBy` is true (the same call and field the floor's
subsumption executor uses).

## 8. Troubleshooting

- **`UnsupportedClassVersionError` / `class file version`:** the JRE is too old for the
  jar. In-container this should not happen (the BFF image ships a JRE 21); on the host,
  install Java 21.
- **MCP client fails with `Extra data: ...` or JSON parse errors:** stdout corruption.
  You are missing the `-Dlogback.configurationFile=/snomed/logback-stderr.xml` argument
  (section 5), or it is not the first thing before `-jar`.
- **`No such file or directory: /snomed/hermes.jar` / empty mount:** the files are not
  where the container looks. Confirm they sit in `./snomed/` next to the compose file
  you launched, then restart; `docker compose exec bff ls /snomed` should list the jar,
  the db, and `logback-stderr.xml`.
- **The tool test hangs or times out:** per-call JVM boot takes 1-2 s on a warm disk but
  the FIRST call against a cold multi-GB db can be slower; retry once. Per-call spawn is
  fine for demos and small runs; for corpus scale run Hermes as a long-lived service
  instead (see `snomed/README.md`).
- **Floor says inconclusive with the tool authored:** that is the designed
  graceful-absence behavior when the spawn fails; re-run the section-7 health check and
  fix what it reports.
