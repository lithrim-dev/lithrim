# `snomed/` — host-supplied stdio MCP server + data (bind-mounted, never committed)

This directory is bind-mounted **read-only** into the BFF container at `/snomed`
(see `docker-compose.yml`, the `bff` service). It is **empty by default** — a stock
`docker compose up` is unaffected. Drop files here to wire a jar-based **stdio MCP
tool** (e.g. Hermes/SNOMED) into a judge's grounding contract.

The contents are licensed and/or multi-GB (SNOMED CT) — **bring your own**. They are
gitignored and are *never* baked into the distributed image.

## Wiring Hermes (SNOMED) as a tool

1. Put the server jar + its db here, e.g.:

   ```
   snomed/
     hermes.jar
     snomed.db        # Hermes db (file or directory)
   ```

2. The BFF image already ships a JRE (`default-jre-headless`, see `Dockerfile.bff`),
   so `java` is available in-container.

3. Author a tool (UI ToolBuilder, or `POST /v1/tools`) with **container** paths —
   the server is spawned *inside* the BFF container, not on the host:

   ```
   COMMAND = java
   ARGS    = -Dlogback.configurationFile=/snomed/logback-stderr.xml -jar /snomed/hermes.jar --db /snomed/snomed.db mcp
   ```

   The `-Dlogback.configurationFile=…` flag is **required**: Hermes' default logging writes
   timestamped lines to STDOUT, which pollutes the MCP JSON-RPC stream (the client fails with
   `Extra data: line 1 column 5`). `logback-stderr.xml` (shipped here) routes logs to STDERR so
   stdout stays pure JSON-RPC.

4. Bind the tool into a flag's `mcp_call` grounding contract (`tool`, `call`,
   `arguments`, `authority`). `McpStdioClient` spawns the jar over stdio per check.

> Per-call JVM boot (~1–2 s) is fine for a small demo, not for corpus scale. For
> scale, run the server as its own HTTP service / hosted MCP instead.
