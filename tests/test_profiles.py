"""Tests for response profile projection."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from luxy import (
    PROFILE_COUNT,
    PROFILE_FULL,
    PROFILE_NAME,
    PROFILE_RESULTS,
    VALID_PROFILES,
)
from luxy.profiles import normalize, project


SAMPLE_PAYLOAD = {
    "@context": "https://linked.art/ns/v1/search.json",
    "id": "https://example.org/search/agent?q=...",
    "type": "OrderedCollectionPage",
    "partOf": [{"id": "https://example.org/...", "totalItems": 42}],
    "orderedItems": [
        {
            "id": "https://example.org/data/person/1",
            "type": "Person",
            "_label": "Rembrandt van Rijn",
        },
        {
            "id": "https://example.org/data/person/2",
            "type": "Person",
            "_label": {"en": ["Jan Vermeer"]},
        },
    ],
}


def test_valid_profiles_set():
    assert VALID_PROFILES == {PROFILE_FULL, PROFILE_RESULTS, PROFILE_NAME, PROFILE_COUNT}


def test_normalize_invalid():
    with pytest.raises(ValueError):
        normalize("nope")


def test_full_profile_is_unchanged():
    out = project(SAMPLE_PAYLOAD, PROFILE_FULL)
    assert out is SAMPLE_PAYLOAD


def test_count_profile():
    out = project(SAMPLE_PAYLOAD, PROFILE_COUNT)
    assert out == {"totalItems": 42}


def test_count_falls_back_to_orderedItems_count():
    payload = {"orderedItems": [{}, {}, {}]}
    out = project(payload, PROFILE_COUNT)
    assert out == {"totalItems": 3}


def test_results_profile_keeps_only_id_and_type():
    out = project(SAMPLE_PAYLOAD, PROFILE_RESULTS)
    assert out["totalItems"] == 42
    assert out["orderedItems"] == [
        {"id": "https://example.org/data/person/1", "type": "Person"},
        {"id": "https://example.org/data/person/2", "type": "Person"},
    ]


def test_name_profile_extracts_labels():
    out = project(SAMPLE_PAYLOAD, PROFILE_NAME)
    assert out["totalItems"] == 42
    assert out["orderedItems"] == [
        {"id": "https://example.org/data/person/1", "label": "Rembrandt van Rijn"},
        {"id": "https://example.org/data/person/2", "label": "Jan Vermeer"},
    ]
