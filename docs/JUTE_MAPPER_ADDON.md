# The JUTE mapper add-on (ingesting arbitrary agent-trace JSON)

The Lithrim Bench **Community Edition is self-contained**: the core, grading (BYOK), and the
clean `make demo` replay run with **no extra services**. You only need the JUTE mapper for one
thing — **ingesting arbitrary / nested agent-trace JSON** (paste a JSON dump → it maps the nested
trace into eval cases → run the council on them).

The mapper is therefore an **opt-in add-on**, not part of the core image: it is a separate
Clojure/JVM service (`../etlp-mapper`, with its own Dockerfile/compose). You run it yourself and
point the CE at it via a single setting — **`LITHRIM_JUTE_URL`**.

## What needs it (and what doesn't)

| Capability                                   | Needs the mapper? |
| -------------------------------------------- | ----------------- |
| `make demo` (offline replay)                 | No                |
| Grading authored cases (BYOK / in-process)   | No                |
| Loading a pack, the conversational shell     | No                |
| **Pasting arbitrary/nested JSON to ingest**  | **Yes**           |

If you never use the "paste arbitrary JSON" ingest, you can ignore this doc entirely.

## How to run it

### 1. Start the mapper

Run the mapper from `../etlp-mapper` (its own Dockerfile/compose), or any compatible mapper.
It serves the JUTE endpoints on port `3031`.

### 2. Point the CE at it — `LITHRIM_JUTE_URL`

Set `LITHRIM_JUTE_URL` to wherever the mapper is reachable **from the BFF**:

| Where the mapper runs                          | `LITHRIM_JUTE_URL`                  |
| ---------------------------------------------- | ----------------------------------- |
| On your host, BFF in Docker                    | `http://host.docker.internal:3031`  |
| As the optional compose `jute` profile service | `http://jute:3031`                  |
| BFF and mapper both on the host (no Docker)    | `http://localhost:3031` (the default) |
| A remote / shared mapper                       | `http://my-mapper.internal:3031`    |

> In Docker, the default `http://localhost:3031` resolves to the **BFF container itself**, which
> has no mapper — so you must set `LITHRIM_JUTE_URL` to a reachable address. With the env **unset**
> the behavior is byte-identical to before (default `localhost:3031`).

The default lives in one place — the `etlp_jute` plugin manifest
(`lithrim_bench/harness/plugins.py`). `LITHRIM_JUTE_URL` overrides it; it is read at call time
(no restart needed beyond a fresh request) and is configuration, not a secret.

### Optional: run the mapper as a compose service

`docker-compose.yml` ships an **optional `jute` profile** that never starts with a plain
`docker compose up` (the core stack is unaffected). Supply your own mapper image:

```bash
JUTE_IMAGE=<your-mapper-image> LITHRIM_JUTE_URL=http://jute:3031 \
  docker compose --profile jute up
```

We do **not** hard-pin a private image — build/supply `JUTE_IMAGE` yourself (e.g. from
`../etlp-mapper`). Without it, run the mapper on the host or remotely and set `LITHRIM_JUTE_URL`
to that address instead.

## Then: the ingest just works

Nothing about the ingest itself changed — only **where the client points**. With the mapper
reachable, the existing paste-JSON flow:

1. you paste an arbitrary / nested agent-trace JSON dump,
2. the DSPy JUTE-gen ingest generates a transform, live-gates it on the mapper, applies it, pins
   it, and upserts the resulting eval cases into your workspace corpus,
3. you run the council on those cases.

See `.env.example` for the `LITHRIM_JUTE_URL` / `JUTE_IMAGE` entries.
