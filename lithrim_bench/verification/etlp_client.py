"""EtlpJuteClient — one injectable wrapper over the live etlp-mapper `:3031` substrate.

The JUTE validator wire contract was previously scattered across `StructuralJuteTool`
(apply-via-id) and `JuteGenValidatorTool` (test-template + generate), and a STALE copy
lives in `lithrim_bench/backends/etlp_structural.py` on `main`. This is the single
source of truth, used by the DSPy validator generator (`jute_dspy.py`) and the
toolbox's persist path.

Wire contract (CONFIRMED live 2026-05-31, against etlp-mapper source):

  GET  /jute-dsl-spec.json                    -> {jute_dsl_spec: {...}}  (the spec the
                                                  Copilot prompt is built from)
  POST /mappings/test-template {template,      -> {compiled, output, error}; in-memory,
       sample_input}                              NO DB. `try-once` applies the template
                                                  to {:resource sample_input}, so pass the
                                                  BARE resource (engine.clj:182).
  POST /mappings {title, content}             -> 201 + Location: /mappings/{id}; empty body.
                                                  `content` MUST be {"yaml": "<template>"}
                                                  (apply reads content.yaml; mappings.clj:24).
  POST /mappings/{id}/apply {data:{resource}} -> {result: {...checks...}}
  PUT  /mappings/{id} {content}               -> update (versioned via history trigger)
  DELETE /mappings/{id}                       -> destroy
  GET  /mappings                              -> [{id, title, content}, ...]

All local calls run as org `lithrim-dev` (auth_component.clj:14); the KB-CDC hook is
skipped when KB_HOOK_SECRET is empty (config.edn:47), so persisting is safe + non-blocking.

RUNTIME BUILTIN GAP (CONFIRMED live): the served DSL spec documents builtins the
runtime does NOT implement — `replace`, `count`, `length`, `size` raise "call nil or
non-function" at apply time. `substr`, `joinStr`, `splitStr`, `toString`, lexicographic
string comparison, and `&&`/`||` short-circuit DO work. This spec-vs-runtime drift is
exactly why a generated validator must be gated on the LIVE bench (test-template), not
on the LLM's confidence or the documented spec.
"""

from __future__ import annotations

import re
from typing import Any

from .tools import StructuralJuteTool

# the id in `Location: http://host:3031/mappings/100` is the LAST path segment, not the
# first integer in the URL (the host's port would mis-parse).
_LOCATION_ID_RE = re.compile(r"/mappings/(\d+)/?$")


class EtlpJuteClient:
    """Thin, injectable HTTP wrapper over the etlp-mapper JUTE endpoints.

    `http_client` is an httpx.Client-like object (`.get/.post/.put/.delete` returning a
    response with `.json()`, `.raise_for_status()`, `.headers`, `.status_code`). When
    omitted, an `httpx.Client` is created lazily and reused for the client's lifetime.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:3031",
        *,
        http_client: Any | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base = base_url.rstrip("/")
        self._client = http_client
        self._timeout = timeout

    # --- lifecycle ------------------------------------------------------- #
    def _http(self) -> Any:
        if self._client is None:
            import httpx

            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    def close(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()

    def health(self) -> bool:
        """True iff the mapper answers at all. Never raises — the ingest front door probes this
        to report "the mapper is not running" honestly instead of a downstream misdiagnosis."""
        try:
            resp = self._http().get(self.base + "/jute-dsl-spec.json")
            return int(getattr(resp, "status_code", 500)) < 500
        except Exception:  # noqa: BLE001 — unreachable/refused/timeout all mean "not healthy"
            return False

    # --- raw verbs ------------------------------------------------------- #
    def _get(self, path: str) -> Any:
        resp = self._http().get(self.base + path)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> Any:
        resp = self._http().post(self.base + path, json=body)
        resp.raise_for_status()
        return resp.json()

    # --- spec ------------------------------------------------------------ #
    def get_dsl_spec(self) -> dict:
        """The JUTE DSL spec (`{jute_dsl_spec: {...}}` unwrapped to the inner dict)."""
        doc = self._get("/jute-dsl-spec.json")
        return doc.get("jute_dsl_spec", doc) if isinstance(doc, dict) else {}

    # --- in-memory compile + apply (no DB) ------------------------------- #
    def test_template(self, template: str, sample_input: Any) -> dict:
        """POST /mappings/test-template. `sample_input` is the BARE resource — the
        engine wraps it as {resource: sample_input} before applying."""
        out = self._post(
            "/mappings/test-template", {"template": template, "sample_input": sample_input}
        )
        return (
            out if isinstance(out, dict) else {"compiled": False, "output": None, "error": str(out)}
        )

    # --- mapping CRUD ---------------------------------------------------- #
    def list_mappings(self) -> list[dict]:
        rows = self._get("/mappings")
        if isinstance(rows, dict):
            rows = rows.get("mappings", [])
        return [m for m in rows if isinstance(m, dict)]

    def find_mapping_by_title(self, title: str) -> dict | None:
        for m in self.list_mappings():
            if (m.get("title") or m.get("name")) == title:
                return m
        return None

    def create_mapping(self, title: str, yaml_template: str) -> dict:
        """POST /mappings. Persists a JUTE template as a mapping and returns
        {id, title, location}. The id is parsed from the 201 Location header."""
        resp = self._http().post(
            self.base + "/mappings",
            json={"title": title, "content": {"yaml": yaml_template}},
        )
        resp.raise_for_status()
        location = resp.headers.get("Location") or resp.headers.get("location") or ""
        m = _LOCATION_ID_RE.search(location)
        if not m:
            raise RuntimeError(f"create_mapping: no mapping id in Location header {location!r}")
        return {"id": int(m.group(1)), "title": title, "location": location}

    def update_mapping(self, mapping_id: int, yaml_template: str) -> None:
        resp = self._http().put(
            self.base + f"/mappings/{mapping_id}",
            json={"content": {"yaml": yaml_template}},
        )
        resp.raise_for_status()

    def apply_mapping(self, mapping_id: int, resource: Any) -> Any:
        """POST /mappings/{id}/apply. `resource` is the bare resource; wrapped as
        {data:{resource: resource}} per the live contract."""
        return self._post(f"/mappings/{mapping_id}/apply", {"data": {"resource": resource}})

    def delete_mapping(self, mapping_id: int) -> None:
        resp = self._http().delete(self.base + f"/mappings/{mapping_id}")
        resp.raise_for_status()

    # --- shared check extraction (single source: StructuralJuteTool) ----- #
    @staticmethod
    def find_checks(applied: Any) -> list[dict]:
        return StructuralJuteTool._find_checks(applied)

    def persist_or_update(self, title: str, yaml_template: str) -> dict:
        """Idempotent persist: create the mapping, or PUT-update it if the title
        already exists (avoids duplicate-title rows; etlp allows dup titles).
        Returns {id, title, action}."""
        existing = self.find_mapping_by_title(title)
        if existing and existing.get("id") is not None:
            self.update_mapping(int(existing["id"]), yaml_template)
            return {"id": int(existing["id"]), "title": title, "action": "updated"}
        created = self.create_mapping(title, yaml_template)
        return {"id": created["id"], "title": title, "action": "created"}
