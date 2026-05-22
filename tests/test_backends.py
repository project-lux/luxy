"""Tests for the pluggable backend layer."""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from luxy import (
    Backend,
    MarkLogicBackend,
    PROFILE_COUNT,
    PROFILE_RESULTS,
    QLeverBackend,
    get_default_backend,
    set_default_backend,
)
from luxy.backends import _UnsupportedQuery, _default_sparql_translator


# ---------------------------------------------------------------------------
# MarkLogicBackend URL-builders
# ---------------------------------------------------------------------------

def test_marklogic_search_url():
    ml = MarkLogicBackend()
    url = ml.search_url("agent", {"AND": [{"name": "Rembrandt"}]})
    assert url.startswith("https://lux.collections.yale.edu/api/search/agent?q=")
    assert "Rembrandt" in url  # urlencoded but the substring survives


def test_marklogic_view_url_uses_friendly_path():
    ml = MarkLogicBackend()
    url = ml.view_url("agent", {"AND": [{"name": "Rembrandt"}]})
    assert "/view/results/people" in url


def test_marklogic_search_url_with_paging():
    ml = MarkLogicBackend()
    url = ml.search_url("item", {"AND": [{"name": "x"}]}, page=3, page_length=50)
    assert "&page=3" in url
    assert "&pageLength=50" in url


def test_marklogic_search_url_with_profile():
    ml = MarkLogicBackend()
    url = ml.search_url("item", {"AND": [{"name": "x"}]}, profile=PROFILE_RESULTS)
    assert "profile=results" in url


# ---------------------------------------------------------------------------
# Default backend management
# ---------------------------------------------------------------------------

def test_default_backend_is_marklogic():
    backend = get_default_backend()
    assert isinstance(backend, MarkLogicBackend)


def test_set_default_backend_round_trip():
    original = get_default_backend()
    try:
        custom = MarkLogicBackend(base_url="https://example.org/api")
        set_default_backend(custom)
        assert get_default_backend() is custom
    finally:
        set_default_backend(original)


# ---------------------------------------------------------------------------
# QLever translator coverage
# ---------------------------------------------------------------------------

def test_translator_simple_leaf():
    sparql = _default_sparql_translator("agent", {"AND": [{"name": "Rembrandt"}]}, 1, 20)
    assert "?s la:name \"Rembrandt\"" in sparql
    assert "LIMIT 20 OFFSET 0" in sparql


def test_translator_multiple_leaves():
    sparql = _default_sparql_translator(
        "agent", {"AND": [{"name": "Rembrandt"}, {"text": "painter"}]}, 2, 10
    )
    assert "LIMIT 10 OFFSET 10" in sparql
    assert "?s la:name \"Rembrandt\"" in sparql
    assert "?s la:text \"painter\"" in sparql


def test_translator_relationship_unsupported():
    with pytest.raises(_UnsupportedQuery):
        _default_sparql_translator(
            "agent", {"AND": [{"produced": {"name": "painting"}}]}, 1, 20
        )


def test_qlever_falls_back_when_unsupported():
    """QLever should hand off to the supplied fallback when it can't translate."""
    calls = []

    class StubFallback(Backend):
        name = "stub"

        def search(self, scope, query, *, page, page_length, profile):
            calls.append({"scope": scope, "query": query, "page": page, "profile": profile})
            return {"totalItems": 0, "orderedItems": []}

        def search_url(self, scope, query, *, page=None, page_length=None, profile="full"):
            return "stub://"

        def document(self, uri, *, profile="full"):
            return {"id": uri}

    qlever = QLeverBackend(fallback=StubFallback())
    result = qlever.search("agent", {"AND": [{"produced": {"name": "x"}}]})
    assert result == {"totalItems": 0, "orderedItems": []}
    assert len(calls) == 1


def test_qlever_no_fallback_raises():
    qlever = QLeverBackend(fallback=None)
    with pytest.raises(NotImplementedError):
        qlever.search("agent", {"AND": [{"produced": {"name": "x"}}]})
