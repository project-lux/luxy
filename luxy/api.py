"""High-level luxy API.

Every query luxy builds is a real :class:`luxql.LuxAPI` tree. There is no
parallel dict / nodes representation: the luxql tree is the query, and
JSON serialisation goes through ``LuxAPI.to_json()``.

The classes in this module (:class:`PeopleGroups`, :class:`Objects`, ...)
are thin wrappers over a luxql tree. They expose a fluent
``filter(...).get()`` interface that:

1. Validates the new filter against the LUX advanced-search-config
   (because luxql does it for free).
2. Attaches the corresponding nodes directly to the in-progress luxql
   tree.
3. When ``.get()`` is called, computes the query complexity, picks the
   appropriate rate-limit bucket, asks the configured backend for the
   result, and applies the requested response profile.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
from typing import Any, Optional

import requests
from luxql import LuxAPI, LuxBoolean, LuxLeaf, LuxRelationship  # noqa: F401

from . import complexity as _complexity
from . import profiles as _profiles
from .backends import Backend, MarkLogicBackend, get_default_backend
from .query import (
    BOOLEAN_KEYS,
    DEFAULT_TEXT_FIELD,
    Chain,
    FilterBuilder,
    QueryBuildError,
    apply_filters,
)
from .rate_limiter import (
    REQUEST_DOCUMENT,
    REQUEST_SIMPLE,
    RateLimiter,
    get_default_rate_limiter,
)

logger = logging.getLogger(__name__)

__version__ = "0.1.0"


config = dict(
    lux_url="https://lux.collections.yale.edu/api",
    max_retries=3,
    retry_backoff_factor=0.3,
    default="item",
    objects="item",
    works="work",
    people="agent",
    places="place",
    concepts="concept",
    events="event",
    set="set",
    lux_config="https://lux.collections.yale.edu/api/advanced-search-config",
    default_field=DEFAULT_TEXT_FIELD,
)

_cached_lux_config = None


def _create_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": f"Mozilla/5.0 (compatible; luxy/{__version__}; +https://github.com/project-lux/luxy)",
        "Accept": "application/json",
    })
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    retry = Retry(
        total=config["max_retries"],
        backoff_factor=config["retry_backoff_factor"],
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


session = _create_session()


def _load_local_config():
    config_path = os.path.join(os.path.dirname(__file__), "..", "docs", "config.json")
    config_path = os.path.normpath(config_path)
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return None


def get_lux_config():
    """Fetch the LUX advanced search config (cached, with offline fallback)."""
    global _cached_lux_config
    if _cached_lux_config is not None:
        return _cached_lux_config

    logger.info("Fetching current Lux config...")
    try:
        response = session.get(config["lux_config"])
        response.raise_for_status()
        _cached_lux_config = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning(
            "Could not fetch remote Lux config (%s), falling back to local copy.",
            exc,
        )
        _cached_lux_config = _load_local_config()
        if _cached_lux_config is None:
            raise ConnectionError(
                "Failed to fetch the Lux config from the API and no local fallback found. "
                "Check your network connection or reinstall luxy."
            ) from exc
    return _cached_lux_config


def clear_lux_config_cache():
    global _cached_lux_config
    _cached_lux_config = None


# ---------------------------------------------------------------------------
# BaseLux
# ---------------------------------------------------------------------------


class BaseLux:
    """Base class for every LUX scope wrapper.

    Subclasses (``PeopleGroups``, ``Objects``, ...) only need to set
    ``self.name`` to the appropriate scope identifier.

    Internally the instance owns a single luxql tree::

        LuxAPI(scope)
          LuxBoolean("AND")        # self._root
            <each filter() call adds direct children here>

    There is no parallel dict / list representation: every operation goes
    through luxql, every JSON we hand back is the result of
    ``api.to_json()``.
    """

    name: str = "item"  # default scope; subclasses override in __init__

    def __init__(
        self,
        backend: Optional[Backend] = None,
        *,
        rate_limiter: Optional[RateLimiter] = None,
        profile: str = _profiles.PROFILE_FULL,
    ):
        self.base_url = config["lux_url"]
        self.page_size = 20
        self._cached_response = None
        self._cached_query_dict = None
        self.backend = backend or get_default_backend()
        self.rate_limiter = rate_limiter or get_default_rate_limiter()
        self.profile = _profiles.normalize(profile)

        # The luxql tree this instance is building. We keep both the API
        # root (so we can re-export the JSON) and the AND boolean (so
        # subsequent filter() calls can attach to it).
        self._api: LuxAPI = LuxAPI(self.name)
        self._root: LuxBoolean = LuxBoolean("AND", parent=self._api)

        # Convenience entry points for relationship-style FilterBuilder usage.
        self.memberOf = FilterBuilder(["memberOf"])
        self.partOf = FilterBuilder(["partOf"])
        self.broader = FilterBuilder(["broader"])

    # -- Dynamic FilterBuilder access ----------------------------------------

    def __getattr__(self, name):
        # Anything that isn't a real attribute becomes the start of a chain
        # so the legacy ``Objects().produced.classification.name(...)``
        # style still works.
        if name.startswith("_") or name in self.__dict__:
            raise AttributeError(name)
        return FilterBuilder([name])

    # -- Configuration helpers -----------------------------------------------

    def with_backend(self, backend: Backend) -> "BaseLux":
        self.backend = backend
        return self

    def with_profile(self, profile: str) -> "BaseLux":
        self.profile = _profiles.normalize(profile)
        return self

    def with_rate_limiter(self, limiter: RateLimiter) -> "BaseLux":
        self.rate_limiter = limiter
        return self

    # -- Query construction --------------------------------------------------

    def filter(self, **kwargs) -> "BaseLux":
        """Add one or more filter conditions to the query.

        Supports:

        * Plain leaves: ``filter(name="John")``
        * Booleans: ``filter(OR=[...])``, ``filter(AND=[...])``,
          ``filter(NOT=[...])``
        * Tuple-style numeric/date comparators:
          ``filter(activeDate=("1700-01-01T00:00:00.000Z", ">"))``
        * Single-hop relationships: ``filter(produced=Objects().filter(name="painting"))``
        * **Graph-style multi-hop chains** via ``__``:
          ``filter(produced__classification__name="painting")``
        * Comparator aliases: ``filter(activeDate__gt=date)``,
          ``filter(height__gte=1)``

        Every kwarg becomes one (and only one) direct child of the root
        ``AND`` boolean. luxql validates each addition against the LUX
        advanced-search-config, so invalid fields / types are caught
        synchronously here rather than at network time.
        """
        try:
            apply_filters(self._root, kwargs)
        except QueryBuildError as exc:
            raise ValueError(str(exc)) from exc
        return self

    # -- Internal: tree composition ------------------------------------------

    def _copy_filters_into(self, parent) -> None:
        """Attach this query's pending filters under another luxql parent.

        This is used when a :class:`BaseLux` instance shows up as a value
        of ``filter(...)`` or as a member of ``OR=[...]`` / ``AND=[...]``.
        We rebuild the children from the JSON of our root AND so that
        each parent gets its own freshly-validated copy.
        """
        if not self._root.children:
            return
        # If we have a single child, attach it directly. Otherwise wrap in
        # an AND so the semantics ("all of these conditions") are preserved.
        for child in self._root.children:
            _attach_json_subtree(parent, child.to_json())

    # -- Execution -----------------------------------------------------------

    def get(self, *, profile: Optional[str] = None) -> "BaseLux":
        if not self._root.children:
            raise ValueError(
                "No filters specified. Please add at least one filter before calling get()"
            )

        query_dict = self.to_dict()
        if self._cached_response is not None and self._cached_query_dict == query_dict:
            logger.warning("Returning cached data...")
            return self

        active_profile = _profiles.normalize(profile or self.profile)
        category = self._category_for_query()
        self.rate_limiter.acquire(category)

        payload = self.backend.search(
            self.name,
            query_dict,
            page=1,
            page_length=self.page_size,
            profile=active_profile,
        )

        self._cached_query_dict = query_dict
        self._cached_response = payload
        self.url = self.backend.search_url(self.name, query_dict)
        self.view_url = self.backend.view_url(self.name, query_dict)
        self.complexity = self.query_complexity()
        self.rate_limit_category = category
        self.json = payload
        self.num_results = self.get_num_results(payload)
        return self

    # -- luxql / JSON views --------------------------------------------------

    def to_luxql(self) -> LuxAPI:
        """Return the luxql tree this query has built up so far."""
        return self._api

    def to_dict(self) -> dict:
        """Return the JSON-serialisable LUX query dict for this query.

        Equivalent to ``self.to_luxql().to_json()`` but tolerates an
        empty query (returning ``{}``).
        """
        if not self._root.children:
            return {}
        return self._api.to_json()

    def query_complexity(self) -> int:
        """Return a numeric complexity score for the current query."""
        return _complexity.score(self._api)

    def _category_for_query(self) -> str:
        return _complexity.category_for(self.query_complexity())

    # -- Cache and result helpers --------------------------------------------

    def clear_cache(self):
        self._cached_response = None
        self._cached_query_dict = None
        return self

    def get_json(self, response):
        if isinstance(response, dict):
            return response
        return response.json()

    def get_num_results(self, json_payload):
        try:
            return json_payload["partOf"][0]["totalItems"]
        except (KeyError, IndexError, TypeError):
            try:
                return int(json_payload.get("totalItems", 0))
            except (TypeError, ValueError):
                logger.warning("Could not find total items in response")
                return 0

    def num_pages(self):
        if not self.page_size:
            return 0
        return (self.num_results // self.page_size) + (
            1 if self.num_results % self.page_size else 0
        )

    def get_page_urls(self):
        if not getattr(self, "url", None):
            raise RuntimeError("Call .get() before requesting page URLs")
        return [f"{self.url}&page={p}" for p in range(1, self.num_pages() + 1)]

    def get_page_data(self, page_url, *, profile: Optional[str] = None):
        active_profile = _profiles.normalize(profile or self.profile)
        # Page fetching is just another search and is rate-limited the same way.
        category = getattr(self, "rate_limit_category", REQUEST_SIMPLE)
        self.rate_limiter.acquire(category)
        response = session.get(page_url)
        response.raise_for_status()
        payload = response.json()
        if active_profile != _profiles.PROFILE_FULL:
            payload = _profiles.project(payload, active_profile)
        return payload

    def get_page_data_all(self, start_page=0, end_page=None):
        if start_page > self.num_pages():
            logger.warning(
                "Start page is greater than the number of pages (%s). Setting start page to %s",
                self.num_pages(),
                self.num_pages() - 1,
            )
            start_page = self.num_pages() - 1
        if end_page is None or end_page > self.num_pages():
            logger.warning(
                "End page is greater than the number of pages (%s). Setting end page to %s",
                self.num_pages(),
                self.num_pages() + 1,
            )
            end_page = self.num_pages() + 1
        for page_url in self.get_page_urls()[start_page:end_page]:
            yield self.get_page_data(page_url)

    def get_items(self, page_data):
        return page_data["orderedItems"]

    def get_item_data(self, item, *, profile: Optional[str] = None):
        # Single-document fetches are unlimited by default.
        active_profile = _profiles.normalize(profile or self.profile)
        self.rate_limiter.acquire(REQUEST_DOCUMENT)
        return self.backend.document(item["id"], profile=active_profile)

    # -- Introspection helpers -----------------------------------------------

    def get_options(self):
        options = get_lux_config()["terms"][self.name]
        formatted = {}
        for key, details in options.items():
            formatted[key] = {
                "label": details.get("label", "No label available"),
                "description": details.get("helpText", "No description available"),
                "relation": details.get("relation", "Unknown type"),
                "allowedOptionsName": details.get("allowedOptionsName", "Unknown type"),
                "defaultOptionsName": details.get("defaultOptionsName", "Unknown type"),
            }
            if "values" in details:
                formatted[key]["values"] = details["values"]
        return formatted

    def list_filters(self):
        options = self.get_options()
        print(f"\nAvailable filters for {self.name}:")
        print("-" * 50)
        for filter_name, details in options.items():
            print(f"\n{filter_name} ({details['label']}) - ({details['relation']}):")
            print(f"  Description: {details['description']}")
            if "values" in details:
                print("  Possible values:")
                for value in details["values"]:
                    print(f"    - {value}")


# ---------------------------------------------------------------------------
# Helper: rebuild luxql nodes from a JSON sub-tree
# ---------------------------------------------------------------------------


def _attach_json_subtree(parent, payload) -> None:
    """Best-effort reconstruction of luxql nodes from a JSON sub-tree.

    Used by :py:meth:`BaseLux._copy_filters_into` so an existing
    :class:`BaseLux` can be embedded inside another query.
    """
    if not isinstance(payload, dict):
        raise QueryBuildError(f"Cannot attach non-dict subtree: {payload!r}")

    keys = [k for k in payload.keys() if not k.startswith("_")]
    if len(keys) != 1:
        raise QueryBuildError(
            f"Expected single top-level key in subtree, got {keys}"
        )
    key = keys[0]
    value = payload[key]

    if key in BOOLEAN_KEYS and isinstance(value, list):
        bl = LuxBoolean(key, parent=parent)
        for child in value:
            _attach_json_subtree(bl, child)
        return
    if isinstance(value, dict):
        rel = LuxRelationship(key, parent=parent)
        # Recurse on the inner subtree, which may itself be a relationship
        # or a leaf-shaped dict ({"name": "x"} or {"_comp": ..., "field": ...}).
        # Detect whether this is a single sub-key relationship/leaf or a
        # multi-key leaf with options like _comp.
        inner_keys = [k for k in value.keys() if not k.startswith("_")]
        if len(inner_keys) == 1 and isinstance(value[inner_keys[0]], (dict, list)):
            _attach_json_subtree(rel, value)
        else:
            # Leaf-with-modifiers, e.g. {"name": "x", "_comp": "=="}
            _build_leaf_from_dict(rel, value)
        return
    # Plain scalar -> leaf at this level
    _build_leaf_from_dict(parent, payload)


def _build_leaf_from_dict(parent, payload: dict) -> None:
    cmpr = payload.get("_comp")
    options = payload.get("_options", []) or []
    weight = payload.get("_weight") or 0
    complete = bool(payload.get("_complete", False))
    fields = [k for k in payload.keys() if not k.startswith("_")]
    if len(fields) != 1:
        raise QueryBuildError(f"Expected single leaf field, got {fields}")
    field = fields[0]
    LuxLeaf(
        field,
        parent=parent,
        value=payload[field],
        comparitor=cmpr,
        options=options,
        weight=weight,
        complete=complete,
    )


# ---------------------------------------------------------------------------
# Concrete scope classes
# ---------------------------------------------------------------------------


class PeopleGroups(BaseLux):
    def __init__(self, **kwargs):
        self.name = config["people"]
        super().__init__(**kwargs)


class Objects(BaseLux):
    def __init__(self, **kwargs):
        self.name = config["objects"]
        super().__init__(**kwargs)


class Works(BaseLux):
    def __init__(self, **kwargs):
        self.name = config["works"]
        super().__init__(**kwargs)


class Places(BaseLux):
    def __init__(self, **kwargs):
        self.name = config["places"]
        super().__init__(**kwargs)


class Concepts(BaseLux):
    def __init__(self, **kwargs):
        self.name = config["concepts"]
        super().__init__(**kwargs)


class Events(BaseLux):
    def __init__(self, **kwargs):
        self.name = config["events"]
        super().__init__(**kwargs)


class Collections(BaseLux):
    def __init__(self, **kwargs):
        self.name = config["set"]
        super().__init__(**kwargs)


__all__ = [
    "BaseLux",
    "Chain",
    "Collections",
    "Concepts",
    "Events",
    "FilterBuilder",
    "Objects",
    "PeopleGroups",
    "Places",
    "Works",
    "clear_lux_config_cache",
    "config",
    "get_lux_config",
]
