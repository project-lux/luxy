"""Smoke tests for the public luxy classes.

luxy now uses luxql for every query, so these tests verify the luxql
representation is built correctly and the JSON it serialises to matches
the LUX wire format.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from luxy import (
    Collections,
    Concepts,
    Events,
    FilterBuilder,
    Objects,
    PeopleGroups,
    Places,
    Works,
)
from luxy.query import Chain


# ---------------------------------------------------------------------------
# FilterBuilder / Chain
# ---------------------------------------------------------------------------

def test_filter_builder_basic():
    fb = FilterBuilder()
    chain = fb.name("John")
    assert isinstance(chain, Chain)
    assert chain.to_json() == {"name": "John"}


def test_filter_builder_nested():
    fb = FilterBuilder()
    chain = fb.produced.classification.name("painting")
    assert chain.to_json() == {"produced": {"classification": {"name": "painting"}}}


def test_filter_builder_depth():
    fb = FilterBuilder()
    chain = fb.memberOf("Letters", depth=2)
    assert chain.to_json() == {"memberOf": {"memberOf": {"text": "Letters"}}}


def test_filter_builder_invalid_depth():
    fb = FilterBuilder()
    chain = fb.memberOf("Letters", depth=0)
    with pytest.raises(ValueError):
        chain.to_json()


# ---------------------------------------------------------------------------
# Base class behaviour
# ---------------------------------------------------------------------------

def test_filter_validation_no_filters():
    obj = Objects()
    with pytest.raises(ValueError):
        obj.get()


def test_basic_filter():
    obj = Objects().filter(name="test").get()
    assert obj._cached_query_dict == {"AND": [{"name": "test"}]}


def test_multiple_filters():
    obj = Objects()
    obj.filter(name="test").filter(hasDigitalImage=True).get()
    # luxql renders booleans as the strings "1"/"0" so they round-trip
    # cleanly through the wire format.
    assert obj._cached_query_dict == {
        "AND": [{"name": "test"}, {"hasDigitalImage": "1"}]
    }


def test_or_filter():
    obj = Objects()
    obj.filter(OR=[{"name": "test1"}, {"name": "test2"}]).get()
    assert obj._cached_query_dict == {
        "AND": [{"OR": [{"name": "test1"}, {"name": "test2"}]}]
    }


# ---------------------------------------------------------------------------
# Class wiring
# ---------------------------------------------------------------------------

def test_class_initialization():
    classes = [
        (PeopleGroups, "agent"),
        (Objects, "item"),
        (Works, "work"),
        (Places, "place"),
        (Concepts, "concept"),
        (Events, "event"),
        (Collections, "set"),
    ]

    for cls, expected_name in classes:
        instance = cls()
        assert instance.name == expected_name
        assert instance.to_luxql().provides_scope == expected_name


def test_cache_clearing():
    obj = Objects()
    obj.filter(name="test")
    obj._cached_response = "dummy"
    obj._cached_query_dict = {"test": "data"}

    obj.clear_cache()
    assert obj._cached_response is None
    assert obj._cached_query_dict is None


def test_boolean_conversion():
    obj = Objects().filter(hasDigitalImage=True).get()
    assert obj._cached_query_dict == {"AND": [{"hasDigitalImage": "1"}]}

    obj = Objects().filter(hasDigitalImage=False).get()
    assert obj._cached_query_dict == {"AND": [{"hasDigitalImage": "0"}]}
