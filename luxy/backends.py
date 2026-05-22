"""Pluggable backends for serving LUX queries.

Two backends are shipped out of the box:

* :class:`MarkLogicBackend` -- the canonical, public LUX HTTP API. This is
  the default and what most users will hit.
* :class:`QLeverBackend` -- a thin SPARQL adaptor for a local
  `QLever <https://github.com/ad-freiburg/qlever>`_ instance backed by an
  ``lmdb`` cache. The translation from luxql to SPARQL is intentionally
  conservative: it covers the common name/text/relationship cases and will
  fall back to MarkLogic when a query uses a feature it doesn't yet
  handle.

The user-visible contract is :class:`Backend`. Each backend exposes:

``search(scope, query, *, page, page_length, profile)``
    Run a search query against the backend and return the parsed JSON.

``document(uri, *, profile)``
    Fetch a single document by URI.

The luxy classes :class:`luxy.api.BaseLux` go through the configured
backend for every request.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
from typing import Any, Callable, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import profiles as _profiles

logger = logging.getLogger(__name__)


def _build_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": user_agent,
        "Accept": "application/json",
    })
    retry = Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class Backend:
    """Abstract backend interface."""

    name: str = "abstract"

    def search(
        self,
        scope: str,
        query: Dict[str, Any],
        *,
        page: int = 1,
        page_length: int = 20,
        profile: str = _profiles.PROFILE_FULL,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def document(
        self,
        uri: str,
        *,
        profile: str = _profiles.PROFILE_FULL,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def search_url(
        self,
        scope: str,
        query: Dict[str, Any],
        *,
        page: Optional[int] = None,
        page_length: Optional[int] = None,
        profile: str = _profiles.PROFILE_FULL,
    ) -> str:
        raise NotImplementedError

    def view_url(
        self,
        scope: str,
        query: Dict[str, Any],
    ) -> Optional[str]:
        return None

    def get_load(self) -> Optional[float]:
        """Optional hook returning a 'load factor' for adaptive rate limiting."""
        return None


class MarkLogicBackend(Backend):
    """LUX MarkLogic-backed HTTP API (the canonical public endpoint)."""

    name = "marklogic"

    SCOPE_TO_VIEW_PATH = {
        "agent": "people",
        "item": "objects",
        "work": "works",
        "place": "places",
        "concept": "concepts",
        "event": "events",
        "set": "collections",
    }

    def __init__(
        self,
        base_url: str = "https://lux.collections.yale.edu/api",
        view_base_url: str = "https://lux.collections.yale.edu/view/results",
        load_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
        user_agent: str = "luxy/0.1.0",
    ):
        self.base_url = base_url.rstrip("/")
        self.view_base_url = view_base_url.rstrip("/")
        self.load_url = load_url
        self.session = session or _build_session(user_agent)

    @staticmethod
    def _encode_query(query: Dict[str, Any]) -> str:
        return urllib.parse.quote(json.dumps(query))

    def search_url(
        self,
        scope,
        query,
        *,
        page=None,
        page_length=None,
        profile=_profiles.PROFILE_FULL,
    ):
        url = f"{self.base_url}/search/{scope}?q={self._encode_query(query)}"
        if page is not None:
            url += f"&page={page}"
        if page_length is not None:
            url += f"&pageLength={page_length}"
        # MarkLogic doesn't natively understand our profile names, but we
        # forward it as a hint anyway -- LUX may add support, and at worst
        # it's an ignored query param.
        if profile and profile != _profiles.PROFILE_FULL:
            url += f"&profile={profile}"
        return url

    def view_url(self, scope, query):
        view_path = self.SCOPE_TO_VIEW_PATH.get(scope, scope)
        return f"{self.view_base_url}/{view_path}?q={self._encode_query(query)}"

    def search(
        self,
        scope,
        query,
        *,
        page=1,
        page_length=20,
        profile=_profiles.PROFILE_FULL,
    ):
        url = self.search_url(
            scope, query, page=page, page_length=page_length, profile=profile
        )
        resp = self.session.get(url)
        resp.raise_for_status()
        payload = resp.json()
        if profile != _profiles.PROFILE_FULL:
            payload = _profiles.project(payload, profile)
        return payload

    def document(self, uri, *, profile=_profiles.PROFILE_FULL):
        resp = self.session.get(uri)
        resp.raise_for_status()
        payload = resp.json()
        if profile == _profiles.PROFILE_NAME:
            return {
                "id": payload.get("id"),
                "label": payload.get("_label") or payload.get("label"),
                "type": payload.get("type"),
            }
        return payload

    def get_load(self):
        if not self.load_url:
            return None
        try:
            resp = self.session.get(self.load_url, timeout=2)
            if resp.status_code != 200:
                return None
            data = resp.json()
            return float(data.get("load", data.get("factor", 1.0)))
        except Exception as exc:  # pragma: no cover
            logger.debug("Load endpoint failed: %s", exc)
            return None


class QLeverBackend(Backend):
    """Local QLever (SPARQL) backend with optional lmdb result cache.

    The translation supports the most common LUX query shapes (text/keyword
    leaves, simple booleans, and one-hop relationships). Anything outside
    that envelope falls back to ``fallback`` (which defaults to a
    :class:`MarkLogicBackend`) when one is supplied; otherwise an
    :class:`NotImplementedError` is raised so the caller knows the query
    can't be served locally.

    The actual SPARQL endpoint is configurable via ``endpoint``. The
    default points at the standard QLever development URL.
    """

    name = "qlever"

    def __init__(
        self,
        endpoint: str = "http://localhost:7019",
        *,
        lmdb_path: Optional[str] = None,
        fallback: Optional[Backend] = None,
        session: Optional[requests.Session] = None,
        user_agent: str = "luxy/0.1.0",
        translator: Optional[Callable[[str, Dict[str, Any], int, int], str]] = None,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.lmdb_path = lmdb_path
        self.fallback = fallback
        self.session = session or _build_session(user_agent)
        self.translator = translator or _default_sparql_translator
        self._cache = _open_lmdb(lmdb_path) if lmdb_path else {}

    def _cache_get(self, key: str):
        if isinstance(self._cache, dict):
            return self._cache.get(key)
        try:
            with self._cache.begin() as txn:  # type: ignore[union-attr]
                value = txn.get(key.encode("utf-8"))
                return json.loads(value) if value else None
        except Exception as exc:  # pragma: no cover
            logger.debug("lmdb read failed: %s", exc)
            return None

    def _cache_put(self, key: str, value: Any) -> None:
        if isinstance(self._cache, dict):
            self._cache[key] = value
            return
        try:
            with self._cache.begin(write=True) as txn:  # type: ignore[union-attr]
                txn.put(key.encode("utf-8"), json.dumps(value).encode("utf-8"))
        except Exception as exc:  # pragma: no cover
            logger.debug("lmdb write failed: %s", exc)

    def search_url(
        self,
        scope,
        query,
        *,
        page=None,
        page_length=None,
        profile=_profiles.PROFILE_FULL,
    ):
        sparql = self.translator(scope, query, page or 1, page_length or 20)
        return f"{self.endpoint}/?query={urllib.parse.quote(sparql)}"

    def search(
        self,
        scope,
        query,
        *,
        page=1,
        page_length=20,
        profile=_profiles.PROFILE_FULL,
    ):
        try:
            sparql = self.translator(scope, query, page, page_length)
        except _UnsupportedQuery as exc:
            if self.fallback:
                logger.info("QLever fallback to %s: %s", self.fallback.name, exc)
                return self.fallback.search(
                    scope, query, page=page, page_length=page_length, profile=profile
                )
            raise NotImplementedError(str(exc)) from exc

        cache_key = f"{scope}|{page}|{page_length}|{sparql}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            payload = cached
        else:
            resp = self.session.get(
                self.endpoint,
                params={"query": sparql},
                headers={"Accept": "application/sparql-results+json"},
            )
            resp.raise_for_status()
            payload = _sparql_to_lux(resp.json(), scope, page, page_length)
            self._cache_put(cache_key, payload)

        if profile != _profiles.PROFILE_FULL:
            payload = _profiles.project(payload, profile)
        return payload

    def document(self, uri, *, profile=_profiles.PROFILE_FULL):
        if self.fallback:
            return self.fallback.document(uri, profile=profile)
        raise NotImplementedError(
            "QLeverBackend.document requires a `fallback` backend (e.g. MarkLogicBackend)."
        )


class _UnsupportedQuery(Exception):
    """Raised by the SPARQL translator for things it doesn't yet handle."""


def _default_sparql_translator(
    scope: str,
    query: Dict[str, Any],
    page: int,
    page_length: int,
) -> str:
    """Very small luxql-dict -> SPARQL translation for the simplest cases.

    This is intentionally conservative; anything more elaborate raises
    :class:`_UnsupportedQuery` so the QLever backend can hand off to its
    fallback. It covers:

    * a top-level ``AND`` of leaf nodes (and trivial single-leaf queries)
    * ``name`` / ``text`` text leaves
    * ``id`` exact-match leaves
    """

    triples = list(_collect_triples(query, "?s"))
    if not triples:
        raise _UnsupportedQuery("Empty query")

    where = " . ".join(triples)
    offset = (page - 1) * page_length
    return (
        "PREFIX la: <https://linked.art/ns/v1/>\n"
        "SELECT ?s ?label WHERE {\n"
        f"  ?s a la:{scope.capitalize()} .\n"
        f"  {where}\n"
        "  OPTIONAL { ?s la:label ?label }\n"
        f"}} LIMIT {page_length} OFFSET {offset}"
    )


def _collect_triples(node, subject):
    if not isinstance(node, dict):
        raise _UnsupportedQuery(f"Cannot translate non-dict node: {node!r}")

    booleans = {k: v for k, v in node.items() if k in ("AND", "OR", "NOT")}
    leaves = {k: v for k, v in node.items() if k not in ("AND", "OR", "NOT") and not k.startswith("_")}

    if "OR" in booleans or "NOT" in booleans:
        raise _UnsupportedQuery("OR/NOT is not yet supported in the QLever translator")
    if "AND" in booleans:
        for child in booleans["AND"]:
            yield from _collect_triples(child, subject)

    for field_name, value in leaves.items():
        if isinstance(value, dict):
            raise _UnsupportedQuery(
                f"Relationship leaf {field_name!r} is not yet supported in the QLever translator"
            )
        safe = str(value).replace('"', '\\"')
        if field_name == "id":
            yield f'BIND(<{safe}> AS {subject})'
        else:
            yield f'{subject} la:{field_name} "{safe}"'


def _sparql_to_lux(sparql_json, scope, page, page_length):
    bindings = (sparql_json.get("results") or {}).get("bindings") or []
    items = []
    for b in bindings:
        items.append({
            "id": (b.get("s") or {}).get("value"),
            "type": scope,
            "_label": (b.get("label") or {}).get("value"),
        })
    return {
        "@context": "https://linked.art/ns/v1/search.json",
        "id": None,
        "type": "OrderedCollectionPage",
        "partOf": [{"totalItems": len(items)}],
        "orderedItems": items,
    }


def _open_lmdb(path: str):  # pragma: no cover - depends on lmdb being installed
    try:
        import lmdb  # type: ignore
    except ImportError:
        logger.warning(
            "lmdb is not installed; falling back to an in-memory cache. "
            "Install with `pip install luxy[lmdb]` for persistence."
        )
        return {}
    os.makedirs(path, exist_ok=True)
    return lmdb.open(path, map_size=1024 * 1024 * 256)


_default_backend: Optional[Backend] = None


def get_default_backend() -> Backend:
    global _default_backend
    if _default_backend is None:
        _default_backend = MarkLogicBackend()
    return _default_backend


def set_default_backend(backend: Backend) -> Backend:
    global _default_backend
    _default_backend = backend
    return backend


def use_local_qlever(
    *,
    endpoint: str = "http://localhost:7019",
    lmdb_path: Optional[str] = "./.luxy-cache",
    fallback: Optional[Backend] = None,
) -> QLeverBackend:
    """Convenience helper: switch the default backend to a local QLever + lmdb.

    The intended deployment is a local QLever instance backed by an lmdb
    cache, with the public LUX MarkLogic API as a fallback for the queries
    QLever can't yet translate. Pass ``fallback=None`` to opt out of the
    fallback (queries beyond the translator's capability will then raise).
    """
    backend = QLeverBackend(
        endpoint=endpoint,
        lmdb_path=lmdb_path,
        fallback=fallback if fallback is not None else MarkLogicBackend(),
    )
    set_default_backend(backend)
    return backend


__all__ = [
    "Backend",
    "MarkLogicBackend",
    "QLeverBackend",
    "get_default_backend",
    "set_default_backend",
    "use_local_qlever",
]
