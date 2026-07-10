# The JUTE mapper add-on (ingesting arbitrary agent-trace JSON)

The Lithrim **Community Edition is self-contained**: the core, grading (BYOK), and the
clean `make demo` replay run with **no extra services**. The JUTE mapper adds one capability —
**ingesting arbitrary / nested agent-trace JSON** (paste a JSON dump → it maps the nested trace
into eval cases → run the council on them).

As of CE Build C the mapper is **bundled and on by default**: `docker compose up` starts a `jute`
service from a **public, SQLite-backed image** that boots standalone — no auth (OIDC off), no
Postgres, no key. The BFF reaches it over the compose network at **`http://jute:3000`** (the
default), so the paste-arbitrary-JSON ingest works out of the box. It is still a separate
Clojure/JVM service (`../etlp-mapper`); override **`JUTE_IMAGE`** to supply your own, or
**`LITHRIM_JUTE_URL`** to point at a host/remote mapper.

## What needs it (and what doesn't)

| Capability                                   | Needs the mapper? |
| -------------------------------------------- | ----------------- |
| `make demo` (offline replay)                 | No                |
| Grading authored cases (BYOK / in-process)   | No                |
| Loading a pack, the conversational shell     | No                |
| **Pasting arbitrary/nested JSON to ingest**  | **Yes**           |

If you never use the "paste arbitrary JSON" ingest, you can run **core-only**:
`docker compose up bff ui` (skips the mapper entirely).

## The default: bundled, zero-config

`docker compose up` starts the `jute` service automatically:

- **image** — `ghcr.io/etlp-clj/etlp-mapper@sha256:bc2242…` (public; **digest-pinned** to an
  immutable build of the `feat-sqlite-backend` branch tag, resolved 2026-07-09, so `docker compose
  up` stays reproducible even if the tag moves; override with `JUTE_IMAGE` — e.g. the moving
  branch tag, or your own build)
- **boots standalone** — `OIDC_ENABLED=false`, embedded SQLite (`JDBC_URL=jdbc:sqlite:/data/...`),
  no Postgres; serves the JUTE endpoints on container port **`3000`**
- **the BFF reaches it** at **`http://jute:3000`** (the default `LITHRIM_JUTE_URL`), over the
  compose network
- **host publish** `3031:3000` — for debugging/curl from your host (`curl localhost:3031/mappings`)
- **state** persists in the `jute_data` named volume; `docker compose down -v` resets it

Nothing to configure — paste arbitrary JSON and the ingest works.

## Pointing at a different mapper — `LITHRIM_JUTE_URL`

To use your own mapper instead of the bundled one, set `LITHRIM_JUTE_URL` to wherever it is
reachable **from the BFF**:

| Where the mapper runs                       | `LITHRIM_JUTE_URL`                  |
| ------------------------------------------- | ----------------------------------- |
| The bundled compose `jute` service (default)| `http://jute:3000`                  |
| On your host, BFF in Docker                 | `http://host.docker.internal:3031`  |
| BFF and mapper both on the host (no Docker) | `http://localhost:3031`             |
| A remote / shared mapper                    | `http://my-mapper.internal:3031`    |

The default lives in one place — the `etlp_jute` plugin manifest
(`lithrim_bench/harness/plugins.py`), with the compose service overriding it to `http://jute:3000`.
`LITHRIM_JUTE_URL` overrides that; it is read at call time (no restart needed beyond a fresh
request) and is configuration, not a secret.

## Then: the ingest just works

Nothing about the ingest itself changed — only **where the client points**. With the mapper
reachable, the existing paste-JSON flow:

1. you paste an arbitrary / nested agent-trace JSON dump,
2. the DSPy JUTE-gen ingest generates a transform, live-gates it on the mapper, applies it, pins
   it, and upserts the resulting eval cases into your workspace corpus,
3. you run the council on those cases.

See `.env.example` for the `LITHRIM_JUTE_URL` / `JUTE_IMAGE` entries.
