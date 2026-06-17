"""StoryWorldAdminClient — one injectable wrapper over the StoryWorld admin API (NARR-6 P1b).

Clones the injectable shape of :class:`EtlpJuteClient` (``base_url`` + an optional ``http_client``
+ a lazy ``httpx.Client``): a thin HTTP wrapper the connector-config + batch-ingest endpoints
compose over. The owner-supplied ``x-api-key`` is the auth header; it is read at call time from
``out/workspaces/<ws>/.connector_env`` (or env), NEVER hardcoded/committed.

Wire contract (owner-provided, 2026-06-17):

  GET  /api/admin/sessions?limit&offset  -> {items: [...], total: int}   (841 sessions)
  GET  /api/admin/sessions/<id>          -> the session detail dict

``test_connection`` is the read-only validation the connector-config endpoint runs before it
persists the key: a clean 200 returns ``{status: 200, ok: True}``; a non-2xx / timeout / transport
error returns the surfaced status (or 0 on a transport error) with ``ok: False`` — it NEVER raises
or fabricates a clean status.
"""

from __future__ import annotations

from typing import Any

_SESSIONS_PATH = "/api/admin/sessions"


class StoryWorldAdminClient:
    """Thin, injectable HTTP wrapper over the StoryWorld admin endpoints.

    ``http_client`` is an httpx.Client-like object (``.get`` returning a response with
    ``.json()``, ``.raise_for_status()``, ``.status_code``). When omitted, an ``httpx.Client``
    is created lazily and reused for the client's lifetime. ``api_key`` rides the ``x-api-key``
    header on every request (mirrors the KB tools' env-sourced secret).
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str,
        http_client: Any | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base = base_url.rstrip("/")
        self._api_key = api_key
        self._client = http_client
        self._timeout = timeout

    # --- lifecycle ------------------------------------------------------- #
    def _http(self) -> Any:
        if self._client is None:
            import httpx

            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self._api_key}

    def close(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()

    # --- raw verb -------------------------------------------------------- #
    def _get(self, path: str, params: dict | None = None) -> Any:
        resp = self._http().get(self.base + path, headers=self._headers(), params=params or {})
        resp.raise_for_status()
        return resp.json()

    # --- sessions -------------------------------------------------------- #
    def list_sessions(self, limit: int = 50, offset: int = 0) -> dict:
        """GET /api/admin/sessions?limit&offset -> {items, total}."""
        out = self._get(_SESSIONS_PATH, {"limit": limit, "offset": offset})
        if isinstance(out, dict):
            return {"items": out.get("items", []), "total": out.get("total", 0)}
        if isinstance(out, list):  # a bare-array shape: degrade gracefully
            return {"items": out, "total": len(out)}
        return {"items": [], "total": 0}

    def get_session(self, session_id: str) -> dict:
        """GET /api/admin/sessions/<id> -> the session detail dict."""
        out = self._get(f"{_SESSIONS_PATH}/{session_id}")
        return out if isinstance(out, dict) else {}

    # --- read-only validation -------------------------------------------- #
    def test_connection(self) -> dict:
        """A read-only Test (GET .../sessions?limit=1). Returns {status, ok}; never raises:
        a non-2xx / timeout / transport error surfaces its status with ok=False."""
        try:
            resp = self._http().get(
                self.base + _SESSIONS_PATH, headers=self._headers(), params={"limit": 1}
            )
        except Exception:  # noqa: BLE001 — a transport error is a Test failure, not a crash
            return {"status": 0, "ok": False}
        status = getattr(resp, "status_code", 0)
        return {"status": int(status), "ok": 200 <= int(status) < 300}
